import json
from typing import Protocol

import httpx
from google import genai
from google.genai import errors, types


class ModelClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...

    def complete_with_tools(
        self, system: str, user: str, tools: list, max_calls: int
    ) -> str: ...


class _BaseClient:
    def _complete_with_tools(
        self,
        client: genai.Client,
        model: str,
        system: str,
        user: str,
        tools: list,
        max_calls: int,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=max_calls
            ),
        )
        for attempt in (1, 2):
            try:
                response = client.models.generate_content(
                    model=model, contents=user, config=config
                )
                return response.text or ""
            except (errors.ServerError, httpx.TransportError):
                if attempt == 2:
                    raise
        return ""

    def _complete_json(
        self, client: genai.Client, model: str, system: str, user: str, schema: dict
    ) -> dict:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        response = None
        for attempt in (1, 2):
            try:
                response = client.models.generate_content(
                    model=model, contents=user, config=config
                )
                break
            except (errors.ServerError, httpx.TransportError):
                if attempt == 2:
                    raise
        if response is None:
            raise RuntimeError("generate_content returned no response")
        result = response.parsed
        if result is None:
            text = response.text
            if not text:
                raise ValueError("model returned empty response")
            result = json.loads(text)
        if not isinstance(result, dict):
            raise TypeError(f"Expected dict, got {type(result).__name__}")
        return result


class GeminiClient(_BaseClient):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        return self._complete_json(self._client, self._model, system, user, schema)

    def complete_with_tools(
        self, system: str, user: str, tools: list, max_calls: int
    ) -> str:
        return self._complete_with_tools(
            self._client, self._model, system, user, tools, max_calls
        )


class FakeClient:
    def __init__(self, responses: list[dict], prose: list[str] | None = None) -> None:
        self._responses = responses
        self._prose = list(prose or [])
        self.calls: list[tuple[str, str, dict]] = []
        self.tool_calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls.append((system, user, schema))
        if not self._responses:
            raise RuntimeError("FakeClient ran out of responses")
        return self._responses.pop(0)

    def complete_with_tools(
        self, system: str, user: str, tools: list, max_calls: int
    ) -> str:
        self.tool_calls.append((system, user))
        if not self._prose:
            raise RuntimeError("FakeClient ran out of prose responses")
        return self._prose.pop(0)
