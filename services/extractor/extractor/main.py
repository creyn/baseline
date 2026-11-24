"""The extractor as a worker: receives from the extract queue until the queue is empty.

Container Apps scales it on the queue length and to zero when idle (ADR-0004).
Settings come from the environment; there are no secrets:

  SERVICEBUS_NAMESPACE          e.g. baseline.servicebus.windows.net
  STORAGE_ACCOUNT_URL           e.g. https://baseline.blob.core.windows.net
  DOCUMENT_INTELLIGENCE_ENDPOINT
  AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
  APPLICATIONINSIGHTS_CONNECTION_STRING (optional; telemetry through OpenTelemetry)
"""
import logging
import os

from . import core, service
from .azure_clients import AzureOpenAILlm, BlobStore, DocumentIntelligenceLayout, StatusSender

LOCK_RENEWAL_SECONDS = 30 * 60


def main():
    from azure.identity import DefaultAzureCredential
    from azure.servicebus import AutoLockRenewer, ServiceBusClient

    credential = DefaultAzureCredential()
    if os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING'):
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(credential=credential, logger_name='extractor')
    logging.basicConfig(level=logging.INFO)

    env = os.environ
    layout = DocumentIntelligenceLayout(env['DOCUMENT_INTELLIGENCE_ENDPOINT'], credential)
    llm = AzureOpenAILlm(env['AZURE_OPENAI_ENDPOINT'], env['AZURE_OPENAI_DEPLOYMENT'],
                         env.get('AZURE_OPENAI_API_VERSION', '2024-10-21'), credential)
    store = BlobStore(env['STORAGE_ACCOUNT_URL'], credential)

    def extract(pages, ids):
        return core.extract(pages, layout, llm, doc_id=ids['docId'], ver_id=ids['verId'],
                            model=env['AZURE_OPENAI_DEPLOYMENT'])

    with ServiceBusClient(env['SERVICEBUS_NAMESPACE'], credential) as bus, \
            bus.get_queue_receiver('extract', max_wait_time=30) as receiver, \
            bus.get_queue_sender('status') as sender, \
            AutoLockRenewer(max_lock_renewal_duration=LOCK_RENEWAL_SECONDS) as renewer:
        status = StatusSender(sender)
        while True:  # Container Apps scales the replica to zero when the queue stays empty
            for message in receiver:
                renewer.register(receiver, message)
                # delivery_count counts earlier attempts, so the first delivery is 1 here (to check on the emulator).
                with _span(message):
                    outcome = service.handle(b''.join(message.body), message.delivery_count + 1, store, status, extract)
                if outcome == service.COMPLETE:
                    receiver.complete_message(message)
                elif outcome == service.ABANDON:
                    receiver.abandon_message(message)
                else:
                    receiver.dead_letter_message(message, reason='unsupported message')


def _span(message):
    """A span that continues the trace of the message (Diagnostic-Id, traceparent format), so the
    logs of this delivery carry the trace id of the user action that started it (ADR-0015)."""
    try:
        from opentelemetry import trace
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    except ImportError:
        import contextlib
        return contextlib.nullcontext()
    props = message.application_properties or {}
    parent = props.get(b'Diagnostic-Id') or props.get('Diagnostic-Id')
    if isinstance(parent, bytes):
        parent = parent.decode('ascii', 'ignore')
    context = TraceContextTextMapPropagator().extract({'traceparent': parent}) if parent else None
    return trace.get_tracer('extractor').start_as_current_span('extract', context=context)


if __name__ == '__main__':
    main()
