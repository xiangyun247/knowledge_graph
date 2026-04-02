#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认知负荷评估API路由（精简版）
完整逻辑在 backend.cognitive.router
"""

from fastapi import APIRouter
from backend.cognitive.router import router as cognitive_router

router = cognitive_router
