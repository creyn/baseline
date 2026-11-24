"""Adapters to Azure: Document Intelligence, Azure OpenAI, Blob Storage, Service Bus.

Every client signs in with Managed Identity (DefaultAzureCredential); there are no keys.
Transient failures become service.Transient, so the message is retried (ADR-0005).
"""
import io
import json

from azure.core.exceptions import (HttpResponseError, ResourceExistsError, ResourceModifiedError,
                                   ResourceNotFoundError, ServiceRequestError, ServiceResponseError)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from .answer import Answer, parse

AI_TIMEOUT_SECONDS = 180
from .layout import box_from_polygon
from .service import Transient


def _transient(error):
    if isinstance(error, (ServiceRequestError, ServiceResponseError)):
        return True
    status = getattr(error, 'status_code', None)
    return status == 429 or (status is not None and status >= 500)


class DocumentIntelligenceLayout:
    """prebuilt-layout on one image-only PDF of all pages, built in memory and never stored (ADR-0007)."""

    def __init__(self, endpoint, credential=None):
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        self.client = DocumentIntelligenceClient(endpoint, credential or DefaultAzureCredential())

    def analyze(self, pages):
        try:
            poller = self.client.begin_analyze_document('prebuilt-layout', body=pdf_of(pages),
                                                        content_type='application/octet-stream')
            result = poller.result(timeout=AI_TIMEOUT_SECONDS)
        except HttpResponseError as e:
            if _transient(e):
                raise Transient('document intelligence') from None
            raise
        except (ServiceRequestError, ServiceResponseError):
            raise Transient('document intelligence') from None
        out = []
        for page in result.pages:  # in the order of the PDF, which is the manifest's order
            out.append([{'text': w.content, 'box': box_from_polygon(w.polygon, page.width, page.height),
                         'confidence': w.confidence} for w in (page.words or [])])
        if len(out) != len(pages):
            raise RuntimeError('Document Intelligence returned a different number of pages')
        return out


def pdf_of(pages):
    """An image-only PDF of the PNG pages, in order."""
    from PIL import Image
    images = [Image.open(io.BytesIO(p.png)).convert('RGB') for p in pages]
    buffer = io.BytesIO()
    images[0].save(buffer, format='PDF', save_all=True, append_images=images[1:], resolution=200)
    return buffer.getvalue()


class AzureOpenAILlm:
    """Structured output with the pydantic model of the answer. Prompts are never logged."""

    def __init__(self, endpoint, deployment, api_version, credential=None):
        from openai import AzureOpenAI
        token = get_bearer_token_provider(credential or DefaultAzureCredential(),
                                          'https://cognitiveservices.azure.com/.default')
        self.client = AzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=token, api_version=api_version,
                                  timeout=AI_TIMEOUT_SECONDS, max_retries=1)
        self.deployment = deployment

    def complete(self, messages):
        import openai
        import pydantic
        unusable = {'results': [], 'documentDates': [], 'fragments': [], 'refused': True}
        try:
            response = self.client.beta.chat.completions.parse(model=self.deployment, messages=messages,
                                                               response_format=Answer)
        except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError):
            raise Transient('azure openai') from None
        except (openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError, pydantic.ValidationError):
            # Cut off, filtered or not in the schema: an invalid answer, retried once by the core.
            return unusable, {'input': 0, 'output': 0}
        choice = response.choices[0]
        usage = {'input': response.usage.prompt_tokens, 'output': response.usage.completion_tokens,
                 'model': getattr(response, 'model', None)}
        if choice.message.refusal or choice.message.content is None:
            return unusable, usage
        try:
            return parse(choice.message.content), usage
        except pydantic.ValidationError:
            return unusable, usage


class BlobStore:
    """clean/{userId}/{docId}/{verId}.zip in, text/{userId}/{docId}/{verId}.json out."""

    def __init__(self, account_url, credential=None):
        from azure.storage.blob import BlobServiceClient
        self.service = BlobServiceClient(account_url, credential=credential or DefaultAzureCredential())

    @staticmethod
    def _name(ids, ext):
        return f'{ids["userId"]}/{ids["docId"]}/{ids["verId"]}.{ext}'

    def _call(self, fn):
        try:
            return fn()
        except (ResourceNotFoundError, ResourceExistsError, ResourceModifiedError):
            raise
        except (HttpResponseError, ServiceRequestError, ServiceResponseError) as e:
            if isinstance(e, HttpResponseError) and not _transient(e):
                raise
            raise Transient('blob storage') from None

    def text_exists(self, ids):
        return self._call(lambda: self.service.get_blob_client('text', self._name(ids, 'json')).exists())

    def read_clean(self, ids):
        blob = self.service.get_blob_client('clean', self._name(ids, 'zip'))
        try:
            return self._call(lambda: blob.download_blob().readall())
        except ResourceNotFoundError:
            return None

    def write_text_if_absent(self, ids, data):
        """If-None-Match: * (overwrite=False): another run that wrote first keeps its blob.

        An existing blob is answered with 409 BlobAlreadyExists; a 412 is handled the same way (to check under a real race).
        """
        blob = self.service.get_blob_client('text', self._name(ids, 'json'))
        try:
            self._call(lambda: blob.upload_blob(data, overwrite=False, content_type='application/json'))
            return True
        except (ResourceExistsError, ResourceModifiedError):
            return False


class StatusSender:
    """The status queue. Sets subject, the docId and verId properties; tracing adds Diagnostic-Id (ADR-0015)."""

    def __init__(self, sender):
        self.sender = sender

    def send(self, msg):
        from azure.servicebus import ServiceBusMessage
        from azure.servicebus.exceptions import ServiceBusError
        message = ServiceBusMessage(json.dumps(msg), content_type='application/json', subject=msg['type'],
                                    application_properties={'docId': msg['docId'], 'verId': msg['verId']})
        try:
            self.sender.send_messages(message)
        except ServiceBusError:
            raise Transient('service bus') from None
