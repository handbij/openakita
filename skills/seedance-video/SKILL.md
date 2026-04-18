---
name: openakita/skills@seedance-video
description: "Generate AI videos using ByteDance Seedance models via Volcengine Ark API. Supports text-to-video, image-to-video (first frame, first+last frame, reference images), audio generation, and draft mode. Use when user wants to generate, create, or produce AI videos from text prompts or images."
license: MIT
metadata:
 author: openakita
 version: "1.0.0"
---

# Seedance Video Generation

Via API Use Seedance Generation AI. 

## Prerequisites

Set ARK_API_KEY: 
export ARK_API_KEY="your-api-key-here"

Base URL: https://ark.cn-beijing.volces.com/api/v3

## Supports

| | ID | |
|------|---------|------|
| Seedance 1.5 Pro | doubao-seedance-1-5-pro-251215 |,,, |
| Seedance 1.0 Pro | doubao-seedance-1-0-pro-250428 |, |
| Seedance 1.0 Lite T2V | doubao-seedance-1-0-lite-t2v-250219 | |
| Seedance 1.0 Lite I2V | doubao-seedance-1-0-lite-i2v-250219 |, |

Default: doubao-seedance-1-5-pro-251215

##

curl -s -X POST "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks" \
 -H "Content-Type: application/json" \
 -H "Authorization: Bearer $ARK_API_KEY" \
 -d '{"model":"doubao-seedance-1-5-pro-251215","content":[{"type":"text","text":"YOUR_PROMPT"}],"ratio":"16:9","duration":5,"resolution":"720p","generate_audio":true}'

## () 

Provides, content type=image_url, role=first_frame. ratio adaptive. 

## () 

Providesand, Set role=first_frame and role=last_frame. 

## Query

curl -s -X GET "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${TASK_ID}" \
 -H "Authorization: Bearer $ARK_API_KEY"

succeeded content.video_url Get. URL 24 have, Download. 

## Parameters

| Parameter | Type | Default | Description |
|------|------|--------|------|
| ratio | string | 16:9 | 16:9, 4:3, 1:1, 3:4, 9:16, 21:9, adaptive |
| duration | int | 5 | (), 4-12 |
| resolution | string | 720p | 480p, 720p, 1080p |
| generate_audio | bool | true | Generation ( 1.5 Pro) |
| draft | bool | false |, ( 1.5 Pro) |

## Notes

- 15
- URL 24, Download
- Task 7
- base64 data URL

## Pre-built Scripts

skill ProvidesExecute Python ( stdlib, ): 

### scripts/seedance.py
Generation CLI, Supports Volcengine Ark and EvoLink. 

```bash
# (Create + + Download) 
python3 scripts/seedance.py create --prompt "" --wait --download ~/Desktop

#
python3 scripts/seedance.py create --prompt "" --image photo.jpg --wait --download ~/Desktop

# 2.0 ( EVOLINK_API_KEY) 
python3 scripts/seedance.py create --prompt "this" --video clip.mp4 --audio bgm.mp3 --wait

#
python3 scripts/seedance.py status <TASK_ID>
```