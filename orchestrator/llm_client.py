"""
Shared LLM client for InvariantOS.
Tries IBM watsonx.ai first (if WATSONX_API_KEY is set), falls back to an
OpenAI-compatible client. This is the ONLY function other agents should use
to talk to an LLM — keep its signature stable after the initial commit.
"""
from __future__ import annotations
import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv

# Resolve .env relative to the repo root (two levels up from this file),
# so it is always found regardless of which directory uvicorn is launched from.
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Raised when the LLM call fails and no fallback is available."""


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def complete(system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """
    Call the LLM and return the response as a plain string.

    Args:
        system_prompt: The system/instruction prompt.
        user_prompt:   The user/content prompt.
        json_mode:     When True, instruct the model to return ONLY raw JSON
                       (no markdown fences, no preamble) and strip any
                       accidental fences before returning.

    Returns:
        The model's text response, cleaned of markdown fences when json_mode=True.

    Raises:
        LLMClientError: if both providers fail.
    """
    if json_mode:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\nIMPORTANT: Return ONLY raw JSON. No markdown fences, no preamble, no commentary."
        )

    watsonx_key = os.getenv("WATSONX_API_KEY", "").strip()
    if watsonx_key:
        try:
            return _call_watsonx(system_prompt, user_prompt, json_mode)
        except Exception as exc:
            logger.warning("watsonx.ai call failed (%s); falling back to OpenAI.", exc)

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            return _call_openai(system_prompt, user_prompt, json_mode)
        except Exception as exc:
            logger.error("OpenAI call failed (%s).", exc)
            raise LLMClientError(f"Both LLM providers failed. Last error: {exc}") from exc

    raise LLMClientError(
        "No LLM credentials found. Set WATSONX_API_KEY or OPENAI_API_KEY in your .env file."
    )


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_watsonx(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    # ASSUMPTION: using ibm-watsonx-ai SDK's ModelInference interface.
    from ibm_watsonx_ai import APIClient, Credentials  # type: ignore
    from ibm_watsonx_ai.foundation_models import ModelInference  # type: ignore
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams  # type: ignore

    credentials = Credentials(
        url=os.environ["WATSONX_URL"],
        api_key=os.environ["WATSONX_API_KEY"],
    )
    client = APIClient(credentials)

    # ASSUMPTION: using meta-llama/llama-3-3-70b-instruct — available on Lite plan
    model = ModelInference(
        model_id="meta-llama/llama-3-3-70b-instruct",
        api_client=client,
        project_id=os.environ.get("WATSONX_PROJECT_ID", ""),
        params={
            GenParams.MAX_NEW_TOKENS: 1024,
            GenParams.TEMPERATURE: 0.1 if json_mode else 0.3,
        },
    )

    full_prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"
    response = model.generate_text(prompt=full_prompt)

    if json_mode:
        response = _strip_markdown_fences(response)
    return response


def _call_openai(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    kwargs: dict = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1 if json_mode else 0.3,
        "max_tokens": 1024,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    text = response.choices[0].message.content or ""

    if json_mode:
        text = _strip_markdown_fences(text)
    return text
