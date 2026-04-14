from openakita.core.agent import Agent


class TestAgentAttachmentHelpers:
    def test_build_desktop_attachment_content_blocks_keeps_text_and_image(self):
        blocks = Agent._build_desktop_attachment_content_blocks(
            [
                {
                    "type": "image",
                    "name": "demo.png",
                    "url": "data:image/png;base64,ZmFrZQ==",
                    "mime_type": "image/png",
                }
            ],
            text="[12:34] 帮我看看这张图",
        )

        assert blocks[0]["type"] == "text"
        assert "帮我看看这张图" in blocks[0]["text"]
        assert blocks[1]["type"] == "image_url"
        assert blocks[1]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_merge_llm_message_content_preserves_multimodal_parts(self):
        merged = Agent._merge_llm_message_content(
            "第一条消息",
            [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}],
        )

        assert isinstance(merged, list)
        assert merged[0]["type"] == "text"
        assert merged[-1]["type"] == "image_url"
