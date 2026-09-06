import os
import sys
import json
import time
import uuid
import threading
from typing import Optional, Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

# Add current dir to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent import (
    OllamaAgent,
    get_anthropic_api_key,
    call_anthropic_messages_api,
    format_messages_for_anthropic,
    CLAUDE_MODELS
)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class OpenAICompatibleHandler(BaseHTTPRequestHandler):
    """
    HTTP Request handler compliant with OpenAI API v1 specs & Anthropic Messages specs:
    - GET /v1/models
    - POST /v1/chat/completions (OpenAI compatible, supports streaming text/event-stream & full response)
    - POST /v1/messages (Anthropic Messages API compatible for Claude & Cline/Roo Code)
    - GET /api/status
    - POST /api/agent/generate
    """

    agent: OllamaAgent = None

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Requested-With, Accept, x-api-key, anthropic-version, anthropic-beta"
        )

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/v1/models":
            self._handle_get_models()
        elif path in ["/api/status", "/status", "/health"]:
            self._handle_get_status()
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Endpoint '{path}' not found."}).encode("utf-8"))

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            body = json.loads(post_data) if post_data.strip() else {}
        except Exception:
            self.send_response(400)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON payload"}).encode("utf-8"))
            return

        if path == "/v1/chat/completions":
            self._handle_chat_completions(body)
        elif path in ("/v1/messages", "/api/claude/messages"):
            self._handle_anthropic_messages(body)
        elif path == "/api/agent/generate":
            self._handle_agent_generate(body)
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Endpoint '{path}' not found."}).encode("utf-8"))

    def _handle_get_models(self):
        try:
            agent = self.agent or OllamaAgent()
            model_names = agent.list_models()
        except Exception:
            model_names = ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "gemma:latest"]

        current_time = int(time.time())
        data = [
            {
                "id": m,
                "object": "model",
                "created": current_time,
                "owned_by": "anthropic" if m.lower().startswith("claude") else "ollama-local",
                "permission": [],
                "root": m,
                "parent": None
            }
            for m in model_names
        ]

        payload = {
            "object": "list",
            "data": data
        }

        resp_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)

    def _handle_get_status(self):
        try:
            agent = self.agent or OllamaAgent()
            models = agent.list_models()
            ollama_online = True
        except Exception:
            models = []
            ollama_online = False

        payload = {
            "status": "online",
            "server": "Ollama Chat & Code Studio API",
            "ollama_online": ollama_online,
            "models_count": len(models),
            "models": models,
            "compatible": "OpenAI v1"
        }
        resp_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)

    def _handle_chat_completions(self, body: Dict[str, Any]):
        model = body.get("model", "qwen2.5-coder:14b")
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        temperature = float(body.get("temperature", 0.2))

        agent = self.agent or OllamaAgent()
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        if model.lower().startswith("claude"):
            api_key = get_anthropic_api_key()
            client_key = self.headers.get("x-api-key", "").strip()
            if client_key and client_key.startswith("sk-ant-"):
                api_key = client_key

            if not api_key:
                err_bytes = json.dumps({"error": {"message": "No Anthropic API key configured for Claude model.", "type": "auth_error"}}).encode("utf-8")
                self.send_response(401)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
                return

            system_msgs = [m.get("content", "") for m in messages if m.get("role") == "system"]
            system_text = "\n\n".join(system_msgs) or "You are a helpful coding assistant."
            user_messages = [m for m in messages if m.get("role") != "system"]

            if stream:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                def on_chunk(piece, full):
                    chunk_payload = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]
                    }
                    self.wfile.write(f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()

                try:
                    call_anthropic_messages_api(
                        api_key=api_key,
                        model=model,
                        messages=format_messages_for_anthropic(user_messages),
                        system_prompt=system_text,
                        stream=True,
                        on_chunk=on_chunk
                    )
                except Exception as e:
                    err_chunk = {"error": {"message": str(e), "type": "server_error"}}
                    self.wfile.write(f"data: {json.dumps(err_chunk)}\n\n".encode("utf-8"))

                final_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                self.close_connection = True
                return
            else:
                try:
                    full_text = call_anthropic_messages_api(
                        api_key=api_key,
                        model=model,
                        messages=format_messages_for_anthropic(user_messages),
                        system_prompt=system_text,
                        stream=False
                    )
                    result = {
                        "id": chat_id,
                        "object": "chat.completion",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": full_text},
                                "finish_reason": "stop"
                            }
                        ],
                        "usage": {"prompt_tokens": 20, "completion_tokens": len(full_text)//4, "total_tokens": 20 + len(full_text)//4}
                    }
                    resp_bytes = json.dumps(result, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp_bytes)))
                    self.end_headers()
                    self.wfile.write(resp_bytes)
                    return
                except Exception as e:
                    err_bytes = json.dumps({"error": {"message": str(e), "type": "api_error"}}).encode("utf-8")
                    self.send_response(500)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err_bytes)))
                    self.end_headers()
                    self.wfile.write(err_bytes)
                    return

        # Support streaming SSE for Continue.dev, Cline, etc.
        if stream:
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            try:
                # Direct streaming from Ollama client
                ollama_stream = agent.client.chat(
                    model=model,
                    messages=messages,
                    stream=True,
                    options={"temperature": temperature}
                )

                for chunk in ollama_stream:
                    delta_content = getattr(chunk.message, "content", "")
                    if delta_content:
                        chunk_payload = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": delta_content},
                                    "finish_reason": None
                                }
                            ]
                        }
                        sse_msg = f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n"
                        self.wfile.write(sse_msg.encode("utf-8"))
                        self.wfile.flush()

                # Send final stop chunk and [DONE]
                final_chunk = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }
                    ]
                }
                self.wfile.write(f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                self.close_connection = True
            except Exception as e:
                err_chunk = {
                    "error": {
                        "message": str(e),
                        "type": "server_error"
                    }
                }
                self.wfile.write(f"data: {json.dumps(err_chunk)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
        else:
            # Non-streaming single response
            try:
                resp = agent.client.chat(
                    model=model,
                    messages=messages,
                    stream=False,
                    options={"temperature": temperature}
                )
                assistant_text = resp.message.content

                result = {
                    "id": chat_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": assistant_text
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": getattr(resp, "prompt_eval_count", 0) or 0,
                        "completion_tokens": getattr(resp, "eval_count", 0) or 0,
                        "total_tokens": (getattr(resp, "prompt_eval_count", 0) or 0) + (getattr(resp, "eval_count", 0) or 0)
                    }
                }
                resp_bytes = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
            except Exception as e:
                err_bytes = json.dumps({"error": {"message": str(e), "type": "api_error"}}).encode("utf-8")
                self.send_response(500)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)

    def _handle_anthropic_messages(self, body: Dict[str, Any]):
        """Handler for Anthropic Messages API v1 (/v1/messages)."""
        model = body.get("model", "claude-3-5-sonnet-20241022")
        messages = body.get("messages", [])
        system = body.get("system", "")
        stream = body.get("stream", False)
        msg_id = f"msg_{uuid.uuid4().hex[:16]}"

        if model.lower().startswith("claude"):
            api_key = get_anthropic_api_key()
            client_key = self.headers.get("x-api-key", "").strip()
            if client_key and client_key.startswith("sk-ant-"):
                api_key = client_key

            if not api_key:
                err_bytes = json.dumps({
                    "type": "error",
                    "error": {"type": "authentication_error", "message": "No Anthropic API key configured. Set via [ 🔑 مفتاح Claude ] or ANTHROPIC_API_KEY."}
                }).encode("utf-8")
                self.send_response(401)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
                return

            if stream:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                start_msg = {
                    "type": "message_start",
                    "message": {
                        "id": msg_id,
                        "type": "message",
                        "role": "assistant",
                        "model": model,
                        "content": [],
                        "stop_reason": None,
                        "usage": {"input_tokens": 10, "output_tokens": 0}
                    }
                }
                self.wfile.write(f"event: message_start\ndata: {json.dumps(start_msg)}\n\n".encode("utf-8"))
                self.wfile.write(b"event: content_block_start\ndata: {\"type\":\"content_block_start\",\"index\":0,\"content_block\":{\"type\":\"text\",\"text\":\"\"}}\n\n")
                self.wfile.flush()

                def on_chunk(piece, full):
                    delta_evt = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": piece}
                    }
                    self.wfile.write(f"event: content_block_delta\ndata: {json.dumps(delta_evt)}\n\n".encode("utf-8"))
                    self.wfile.flush()

                try:
                    call_anthropic_messages_api(
                        api_key=api_key,
                        model=model,
                        messages=format_messages_for_anthropic(messages),
                        system_prompt=system or "You are a helpful coding assistant.",
                        stream=True,
                        on_chunk=on_chunk
                    )
                except Exception as e:
                    err_evt = {"type": "error", "error": {"message": str(e)}}
                    self.wfile.write(f"event: error\ndata: {json.dumps(err_evt)}\n\n".encode("utf-8"))

                self.wfile.write(b"event: content_block_stop\ndata: {\"type\":\"content_block_stop\",\"index\":0}\n\n")
                self.wfile.write(b"event: message_delta\ndata: {\"type\":\"message_delta\",\"delta\":{\"stop_reason\":\"end_turn\"},\"usage\":{\"output_tokens\":20}}\n\n")
                self.wfile.write(b"event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n")
                self.wfile.flush()
                self.close_connection = True
                return
            else:
                try:
                    full_text = call_anthropic_messages_api(
                        api_key=api_key,
                        model=model,
                        messages=format_messages_for_anthropic(messages),
                        system_prompt=system or "You are a helpful coding assistant.",
                        stream=False
                    )
                    resp_obj = {
                        "id": msg_id,
                        "type": "message",
                        "role": "assistant",
                        "model": model,
                        "content": [{"type": "text", "text": full_text}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 15, "output_tokens": len(full_text)//4}
                    }
                    data_bytes = json.dumps(resp_obj, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(data_bytes)))
                    self.end_headers()
                    self.wfile.write(data_bytes)
                except Exception as e:
                    self.send_response(500)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            # Translation layer from Ollama to Anthropic Messages format
            agent = self.agent or OllamaAgent()
            ollama_messages = []
            if system:
                ollama_messages.append({"role": "system", "content": system})
            for m in messages:
                ollama_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

            if stream:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()

                self.wfile.write(f"event: message_start\ndata: {{\"type\":\"message_start\",\"message\":{{\"id\":\"{msg_id}\",\"type\":\"message\",\"role\":\"assistant\",\"model\":\"{model}\",\"content\":[],\"stop_reason\":null}}}}\n\n".encode("utf-8"))
                self.wfile.write(b"event: content_block_start\ndata: {\"type\":\"content_block_start\",\"index\":0,\"content_block\":{\"type\":\"text\",\"text\":\"\"}}\n\n")
                self.wfile.flush()

                try:
                    ollama_stream = agent.client.chat(model=model, messages=ollama_messages, stream=True)
                    for chunk in ollama_stream:
                        piece = getattr(chunk.message, "content", "")
                        if piece:
                            delta_evt = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": piece}}
                            self.wfile.write(f"event: content_block_delta\ndata: {json.dumps(delta_evt)}\n\n".encode("utf-8"))
                            self.wfile.flush()
                except Exception as e:
                    self.wfile.write(f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode("utf-8"))

                self.wfile.write(b"event: content_block_stop\ndata: {\"type\":\"content_block_stop\",\"index\":0}\n\n")
                self.wfile.write(b"event: message_delta\ndata: {\"type\":\"message_delta\",\"delta\":{\"stop_reason\":\"end_turn\"}}\n\n")
                self.wfile.write(b"event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n")
                self.wfile.flush()
                self.close_connection = True
            else:
                try:
                    resp = agent.client.chat(model=model, messages=ollama_messages, stream=False)
                    text = resp.message.content
                    resp_obj = {
                        "id": msg_id,
                        "type": "message",
                        "role": "assistant",
                        "model": model,
                        "content": [{"type": "text", "text": text}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 10, "output_tokens": len(text)//4}
                    }
                    data_bytes = json.dumps(resp_obj, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(data_bytes)))
                    self.end_headers()
                    self.wfile.write(data_bytes)
                except Exception as e:
                    self.send_response(500)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def _handle_agent_generate(self, body: Dict[str, Any]):
        """Dedicated high-level agent endpoint returning structured multi-file bundle."""
        prompt = body.get("prompt", "")
        model = body.get("model", "qwen2.5-coder:14b")
        existing_files = body.get("files", [])

        if not prompt:
            self.send_response(400)
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Prompt cannot be empty."}).encode("utf-8"))
            return

        agent = self.agent or OllamaAgent()
        try:
            res = agent.chat_turn(user_message=prompt, model=model, current_project_files=existing_files)
            resp_bytes = json.dumps(res, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
        except Exception as e:
            err_bytes = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err_bytes)))
            self.end_headers()
            self.wfile.write(err_bytes)

    def log_message(self, format, *args):
        # Silence default terminal request spam
        pass


class LocalAPIServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000, agent: Optional[OllamaAgent] = None):
        self.host = host
        self.port = port
        self.agent = agent or OllamaAgent()
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self._is_running = False

    def start(self):
        if self._is_running:
            return

        # Bind handler with agent
        handler_class = OpenAICompatibleHandler
        handler_class.agent = self.agent

        self.server = ThreadingHTTPServer((self.host, self.port), handler_class)
        self._is_running = True

        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def _run_server(self):
        try:
            self.server.serve_forever()
        except Exception:
            pass
        finally:
            self._is_running = False

    def stop(self):
        if not self._is_running or not self.server:
            return
        self._is_running = False
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass

    def is_running(self) -> bool:
        return self._is_running

    def get_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    def get_base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    print(f"Starting Local OpenAI-Compatible API Server on http://127.0.0.1:{port}/v1 ...")
    server = LocalAPIServer(port=port)
    server.start()
    print("Server running! Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping server...")
        server.stop()
        print("Server stopped.")
