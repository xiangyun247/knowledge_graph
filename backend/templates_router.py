#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据模板下载 API：GET /api/templates/{template_type}
"""

import json
from typing import Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

# 模板内容
TEMPLATE_DISEASE_JSON = json.dumps({
    "diseases": [
        {
            "name": "疾病名称",
            "category": "疾病分类",
            "description": "疾病描述",
            "common_symptoms": ["症状1", "症状2"],
            "department": "就诊科室"
        }
    ]
}, ensure_ascii=False, indent=2)

TEMPLATE_SYMPTOM_CSV = "id,name,severity,description\nsymptom_001,症状名称,轻度/中度/重度,症状描述\n"

TEMPLATE_MEDICINE_JSON = json.dumps({
    "drugs": [
        {
            "name": "药物名称",
            "type": "药物类型",
            "usage": "用法",
            "dosage": "剂量",
            "treats": ["可治疗的疾病"]
        }
    ]
}, ensure_ascii=False, indent=2)

TEMPLATE_RELATION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<knowledge-graph>
  <relation>
    <source>实体ID或名称</source>
    <target>实体ID或名称</target>
    <type>关系类型(如: has_symptom, treated_by)</type>
  </relation>
</knowledge-graph>
"""


def _get_template_content_and_filename(template_type: str) -> Tuple[bytes, str, str]:
    """根据类型返回 (内容字节, 文件名, media_type)。"""
    type_map = {
        "disease": (TEMPLATE_DISEASE_JSON.encode("utf-8"), "疾病数据模板.json", "application/json"),
        "symptom": (TEMPLATE_SYMPTOM_CSV.encode("utf-8"), "症状数据模板.csv", "text/csv"),
        "medicine": (TEMPLATE_MEDICINE_JSON.encode("utf-8"), "药物数据模板.json", "application/json"),
        "relation": (TEMPLATE_RELATION_XML.encode("utf-8"), "关系数据模板.xml", "application/xml"),
    }
    if template_type not in type_map:
        raise ValueError(f"未知模板类型: {template_type}")
    content, filename, media_type = type_map[template_type]
    return content, filename, media_type


router = APIRouter(prefix="/api", tags=["数据模板"])


@router.get("/templates/{template_type}")
async def download_template(template_type: str):
    """
    下载数据模板文件。支持: disease(JSON), symptom(CSV), medicine(JSON), relation(XML)。
    """
    try:
        content, filename, media_type = _get_template_content_and_filename(template_type)
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
