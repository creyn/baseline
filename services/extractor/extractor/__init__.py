"""The extractor: masked pages of a checked version in, the text blob out (ADR-0007).

The core (core.py) and the service shell (service.py) use only the standard library,
so their tests run anywhere. The Azure adapters (azure_clients.py) and the model of
the LLM's answer (answer.py) need the packages in requirements.txt.
"""

VERSION = '0.2.0'
PROMPT_VERSION = 'extract.v2'
