"""Offline protocol diagnostic tests; no real provider requests."""
import json
import unittest
from scripts.probe_openai_chat_protocol import classify_response
from cost_to_done.gateway import UpstreamResponse

class ProtocolDiagnosticTests(unittest.TestCase):
    def test_http_error_reports_codes_but_never_body(self):
        body={"error":{"type":"invalid_request_error",
                       "code":"unsupported_parameter","param":"stream_options",
                       "message":"secret-should-not-be-logged"}}
        result=classify_response(UpstreamResponse(400,json.dumps(body).encode()),"gpt-6.1-terra")
        self.assertEqual(result["upstream_http_status"],400)
        self.assertEqual(result["provider_error_param"],"stream_options")
        self.assertNotIn("secret-should-not-be-logged",str(result))

    def test_stream_alias_diagnostic(self):
        payload=(b'data: {"model":"gpt-6.1-terra-2026-11-23","choices":[{"delta":{"content":"OK"},"finish_reason":"stop"}]}\n\n'
                 b'data: {"model":"gpt-6.1-terra-2026-11-23","choices":[],"usage":{"prompt_tokens":1,"completion_tokens":2}}\n\n'
                 b'data: [DONE]\n\n')
        result=classify_response(UpstreamResponse(200,payload,"text/event-stream"),"gpt-6.1-terra")
        self.assertEqual(result["upstream_reported_model"],"gpt-6.1-terra-2026-11-23")
        self.assertEqual(result["gateway_protocol_result"],"stream_event_model_mismatch")

    def test_nonstandard_success_mime_refused(self):
        out=classify_response(UpstreamResponse(200,b"{}", "application/json"),"gpt-6.2-sol")
        self.assertEqual(out["gateway_protocol_result"],"unexpected_mime")

if __name__=="__main__":
    unittest.main()
