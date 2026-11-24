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

LOCK_RENEWAL_SECONDS = 15 * 60


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
                outcome = service.handle(b''.join(message.body), message.delivery_count, store, status, extract)
                if outcome == service.COMPLETE:
                    receiver.complete_message(message)
                elif outcome == service.ABANDON:
                    receiver.abandon_message(message)
                else:
                    receiver.dead_letter_message(message, reason='unsupported message')


if __name__ == '__main__':
    main()
