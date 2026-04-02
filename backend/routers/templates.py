#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据模板API路由
"""

import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/templates", tags=["数据模板"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")


@router.get("/{template_type}")
async def download_template(template_type: str):
    """下载数据模板"""
    valid_types = ["disease", "symptom", "medicine", "relation"]
    if template_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"无效的模板类型，可选: {valid_types}")

    template_file = os.path.join(TEMPLATE_DIR, f"{template_type}_template.csv")

    if not os.path.exists(template_file):
        raise HTTPException(status_code=404, detail=f"模板文件不存在: {template_type}")

    return FileResponse(
        template_file,
        media_type="text/csv",
        filename=f"{template_type}_template.csv"
    )
