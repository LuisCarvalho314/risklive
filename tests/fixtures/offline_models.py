"""Import-time sentinels: tests must explicitly stub every model boundary."""
import sys
from types import ModuleType


class ForbiddenModel:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Test runtime guard: real model construction")

    @classmethod
    def load(cls, *args, **kwargs):
        raise RuntimeError("Test runtime guard: real model loading")


def install():
    for name, symbol in [("bertopic", "BERTopic"), ("sentence_transformers", "SentenceTransformer"), ("umap", "UMAP"), ("hdbscan", "HDBSCAN")]:
        module = ModuleType(name)
        setattr(module, symbol, ForbiddenModel)
        sys.modules[name] = module
    utils = ModuleType("bertopic._utils")

    def forbidden(*args, **kwargs):
        raise RuntimeError("Test must stub BERTopic distance validation")

    utils.validate_distance_matrix = forbidden
    sys.modules[utils.__name__] = utils
