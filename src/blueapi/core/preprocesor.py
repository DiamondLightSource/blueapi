from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from pydantic import Field

from blueapi.utils import BlueapiBaseModel

from .bluesky_types import PlanWrapper


class PreprocessorApplicationPolicy(str, Enum):
    """
    A policy used to determine when to apply a preprocessor to a plan
    """

    ALWAYS = "ALWAYS"
    NEVER = "NEVER"


class PreprocessorModel(BlueapiBaseModel):
    """
    Description of a preprocessor that can be applied to plans
    """

    name: str = Field(description="Name of the preprocessor")
    description: Optional[str] = Field(
        description="Optional extended description of the preprocessor and its function"
    )
    application_policy: PreprocessorApplicationPolicy = Field(
        description="Policy that determines whether this preprocessor should be "
        "applied to a plan",
    )


class PreprocessorModelQueryResponse(BlueapiBaseModel):
    models: List[PreprocessorModel]


@dataclass
class PlanPreprocessor:
    model: PreprocessorModel
    wrapper: PlanWrapper
