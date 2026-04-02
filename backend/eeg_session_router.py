#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EEG 会话管理路由

提供受试者管理和监测会话管理 API
"""

import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db.mysql_client import MySQLClient
from loguru import logger

router = APIRouter(prefix="/api/eeg-session", tags=["EEG会话管理"])


def get_mysql() -> MySQLClient:
    """获取 MySQL 客户端"""
    client = MySQLClient()
    client.connect()
    return client


class SubjectCreate(BaseModel):
    subject_code: str
    name: Optional[str] = None
    age: int
    gender: str
    cognitive_status: str = "normal"
    remark: Optional[str] = None


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    cognitive_status: Optional[str] = None
    remark: Optional[str] = None


class SessionCreate(BaseModel):
    subject_id: int
    session_note: Optional[str] = None


class SessionEnd(BaseModel):
    duration_seconds: int
    avg_score: float
    avg_theta_beta: float
    avg_alpha_beta: float
    avg_theta_power: float
    avg_alpha_power: float
    avg_beta_power: float
    avg_snr: float
    score_trend: List[float]
    cognitive_level: str
    session_note: Optional[str] = None


@router.get("/subjects")
def get_subjects(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    cognitive_status: Optional[str] = Query(None, description="认知状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000)
):
    """获取受试者列表"""
    mysql = get_mysql()
    try:
        conditions = []
        params = []
        if keyword:
            conditions.append("(subject_code LIKE :keyword OR name LIKE :keyword)")
            params.append({"keyword": f"%{keyword}%"})
        if cognitive_status:
            conditions.append("cognitive_status = :status")
            params.append({"status": cognitive_status})

        where = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        count_query = f"SELECT COUNT(*) as total FROM eeg_subjects WHERE {where}"
        total = mysql.execute_query(count_query, dict(zip([p for p in params if isinstance(p, dict)], [v for p in params for v in p.values()])))[0]["total"]

        query = f"""
            SELECT * FROM eeg_subjects
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        params_dict = {}
        for p in params:
            if isinstance(p, dict):
                params_dict.update(p)
        params_dict["limit"] = page_size
        params_dict["offset"] = offset

        subjects = mysql.execute_query(query, params_dict)
        subjects = [dict(s) for s in subjects]

        for s in subjects:
            if s.get("created_at"):
                s["created_at"] = s["created_at"].isoformat()
            if s.get("updated_at"):
                s["updated_at"] = s["updated_at"].isoformat()

        return {"total": total, "subjects": subjects, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"获取受试者列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.get("/subjects/{subject_id}")
def get_subject(subject_id: int):
    """获取单个受试者"""
    mysql = get_mysql()
    try:
        result = mysql.execute_query("SELECT * FROM eeg_subjects WHERE id = :id", {"id": subject_id})
        if not result:
            raise HTTPException(status_code=404, detail="受试者不存在")
        subject = result[0]
        if subject.get("created_at"):
            subject["created_at"] = subject["created_at"].isoformat()
        if subject.get("updated_at"):
            subject["updated_at"] = subject["updated_at"].isoformat()
        return subject
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取受试者失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.post("/subjects")
def create_subject(data: SubjectCreate):
    """创建受试者"""
    mysql = get_mysql()
    try:
        mysql.execute_update("""
            INSERT INTO eeg_subjects (subject_code, name, age, gender, cognitive_status, remark)
            VALUES (:subject_code, :name, :age, :gender, :cognitive_status, :remark)
        """, {
            "subject_code": data.subject_code,
            "name": data.name,
            "age": data.age,
            "gender": data.gender,
            "cognitive_status": data.cognitive_status,
            "remark": data.remark
        })

        result = mysql.execute_query("SELECT LAST_INSERT_ID() as id")
        subject_id = result[0]["id"] if result else 0

        return {"id": subject_id, "subject_code": data.subject_code}
    except Exception as e:
        error_msg = str(e)
        if "Duplicate entry" in error_msg and "subject_code" in error_msg:
            raise HTTPException(status_code=400, detail=f"受试者编号 '{data.subject_code}' 已存在，请使用其他编号")
        logger.error(f"创建受试者失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.put("/subjects/{subject_id}")
def update_subject(subject_id: int, data: SubjectUpdate):
    """更新受试者"""
    mysql = get_mysql()
    try:
        updates = []
        params = {}
        if data.name is not None:
            updates.append("name = :name")
            params["name"] = data.name
        if data.age is not None:
            updates.append("age = :age")
            params["age"] = data.age
        if data.gender is not None:
            updates.append("gender = :gender")
            params["gender"] = data.gender
        if data.cognitive_status is not None:
            updates.append("cognitive_status = :cognitive_status")
            params["cognitive_status"] = data.cognitive_status
        if data.remark is not None:
            updates.append("remark = :remark")
            params["remark"] = data.remark

        if not updates:
            raise HTTPException(status_code=400, detail="没有要更新的字段")

        params["id"] = subject_id
        query = f"UPDATE eeg_subjects SET {', '.join(updates)} WHERE id = :id"
        mysql.execute_update(query, params)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新受试者失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int):
    """删除受试者"""
    mysql = get_mysql()
    try:
        mysql.execute_update("DELETE FROM eeg_subjects WHERE id = :id", {"id": subject_id})
        return {"success": True}
    except Exception as e:
        logger.error(f"删除受试者失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.post("/sessions")
def create_session(data: SessionCreate):
    """创建监测会话（开始监测）"""
    mysql = get_mysql()
    try:
        result = mysql.execute_query("SELECT id FROM eeg_subjects WHERE id = :id", {"id": data.subject_id})
        if not result:
            raise HTTPException(status_code=404, detail="受试者不存在")

        mysql.execute_update("""
            INSERT INTO eeg_sessions (subject_id, session_note)
            VALUES (:subject_id, :session_note)
        """, {
            "subject_id": data.subject_id,
            "session_note": data.session_note
        })

        result = mysql.execute_query("SELECT LAST_INSERT_ID() as id")
        session_id = result[0]["id"] if result else 0

        result = mysql.execute_query("SELECT start_time FROM eeg_sessions WHERE id = :id", {"id": session_id})
        start_time = result[0]["start_time"].isoformat() if result else ""
        return {"session_id": session_id, "start_time": start_time}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.post("/sessions/{session_id}/end")
def end_session(session_id: int, data: SessionEnd):
    """结束监测会话"""
    mysql = get_mysql()
    try:
        result = mysql.execute_query("SELECT * FROM eeg_sessions WHERE id = :id", {"id": session_id})
        if not result:
            raise HTTPException(status_code=404, detail="会话不存在")
        if result[0]["status"] == "completed":
            raise HTTPException(status_code=400, detail="会话已结束")

        mysql.execute_update("""
            UPDATE eeg_sessions SET
                end_time = NOW(),
                duration_seconds = :duration_seconds,
                avg_score = :avg_score,
                avg_theta_beta = :avg_theta_beta,
                avg_alpha_beta = :avg_alpha_beta,
                avg_theta_power = :avg_theta_power,
                avg_alpha_power = :avg_alpha_power,
                avg_beta_power = :avg_beta_power,
                avg_snr = :avg_snr,
                score_trend = :score_trend,
                cognitive_level = :cognitive_level,
                session_note = :session_note,
                status = 'completed'
            WHERE id = :id
        """, {
            "duration_seconds": data.duration_seconds,
            "avg_score": data.avg_score,
            "avg_theta_beta": data.avg_theta_beta,
            "avg_alpha_beta": data.avg_alpha_beta,
            "avg_theta_power": data.avg_theta_power,
            "avg_alpha_power": data.avg_alpha_power,
            "avg_beta_power": data.avg_beta_power,
            "avg_snr": data.avg_snr,
            "score_trend": json.dumps(data.score_trend),
            "cognitive_level": data.cognitive_level,
            "session_note": data.session_note,
            "id": session_id
        })
        return {"success": True, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"结束会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.get("/sessions")
def get_sessions(
    subject_id: Optional[int] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000)
):
    """获取会话列表"""
    mysql = get_mysql()
    try:
        conditions = []
        params = {}
        if subject_id:
            conditions.append("s.subject_id = :subject_id")
            params["subject_id"] = subject_id
        if start_time:
            conditions.append("s.start_time >= :start_time")
            params["start_time"] = start_time
        if end_time:
            conditions.append("s.start_time <= :end_time")
            params["end_time"] = end_time

        where = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        count_query = f"SELECT COUNT(*) as total FROM eeg_sessions s WHERE {where}"
        total = mysql.execute_query(count_query, params)[0]["total"]

        query = f"""
            SELECT s.*, sub.subject_code, sub.name as subject_name
            FROM eeg_sessions s
            LEFT JOIN eeg_subjects sub ON s.subject_id = sub.id
            WHERE {where}
            ORDER BY s.start_time DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = offset

        sessions = mysql.execute_query(query, params)
        sessions = [dict(s) for s in sessions]

        for s in sessions:
            if s.get("start_time"):
                s["start_time"] = s["start_time"].isoformat()
            if s.get("end_time"):
                s["end_time"] = s["end_time"].isoformat()
            if s.get("created_at"):
                s["created_at"] = s["created_at"].isoformat()

        return {"total": total, "sessions": sessions, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.get("/sessions/summary")
def get_session_summary(
    group_by: str = Query("subject", enum=["subject", "status", "date"]),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """获取汇总统计"""
    mysql = get_mysql()
    try:
        conditions = []
        params = {}
        if start_date:
            conditions.append("start_time >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("start_time <= :end_date")
            params["end_date"] = end_date

        where = " AND ".join(conditions) if conditions else "1=1"

        if group_by == "subject":
            query = f"""
                SELECT
                    subject_id,
                    subject_code,
                    subject_name,
                    COUNT(*) as session_count,
                    AVG(avg_score) as avg_score,
                    AVG(duration_seconds) as avg_duration,
                    AVG(avg_theta_beta) as avg_theta_beta,
                    AVG(avg_alpha_beta) as avg_alpha_beta
                FROM (
                    SELECT s.*, sub.subject_code, sub.name as subject_name
                    FROM eeg_sessions s
                    LEFT JOIN eeg_subjects sub ON s.subject_id = sub.id
                    WHERE {where}
                ) t
                GROUP BY subject_id, subject_code, subject_name
            """
        elif group_by == "status":
            query = f"""
                SELECT status, COUNT(*) as count, AVG(avg_score) as avg_score
                FROM eeg_sessions WHERE {where}
                GROUP BY status
            """
        else:
            query = f"""
                SELECT
                    DATE(start_time) as date,
                    COUNT(*) as session_count,
                    AVG(avg_score) as avg_score,
                    AVG(duration_seconds) as avg_duration
                FROM eeg_sessions WHERE {where}
                GROUP BY DATE(start_time)
                ORDER BY date DESC
            """

        results = mysql.execute_query(query, params)
        return {"group_by": group_by, "data": results}
    except Exception as e:
        logger.error(f"获取汇总失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.get("/sessions/{session_id}")
def get_session(session_id: int):
    """获取单个会话"""
    mysql = get_mysql()
    try:
        result = mysql.execute_query("""
            SELECT s.*, sub.subject_code, sub.name as subject_name
            FROM eeg_sessions s
            LEFT JOIN eeg_subjects sub ON s.subject_id = sub.id
            WHERE s.id = :id
        """, {"id": session_id})
        if not result:
            raise HTTPException(status_code=404, detail="会话不存在")
        session = result[0]
        if session.get("start_time"):
            session["start_time"] = session["start_time"].isoformat()
        if session.get("end_time"):
            session["end_time"] = session["end_time"].isoformat()
        if session.get("created_at"):
            session["created_at"] = session["created_at"].isoformat()
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int):
    """删除会话"""
    mysql = get_mysql()
    try:
        mysql.execute_update("DELETE FROM eeg_sessions WHERE id = :id", {"id": session_id})
        return {"success": True}
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()


@router.post("/sessions/export")
def export_sessions(
    subject_ids: Optional[List[int]] = None,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """导出数据为 CSV"""
    mysql = get_mysql()
    try:
        conditions = []
        params = {}
        if subject_ids:
            placeholders = ",".join([f":id{i}" for i in range(len(subject_ids))])
            conditions.append(f"subject_id IN ({placeholders})")
            for i, sid in enumerate(subject_ids):
                params[f"id{i}"] = sid
        if start_date:
            conditions.append("start_time >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("start_time <= :end_date")
            params["end_date"] = end_date

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = mysql.execute_query(f"""
            SELECT s.*, sub.subject_code, sub.name, sub.age, sub.gender, sub.cognitive_status
            FROM eeg_sessions s
            LEFT JOIN eeg_subjects sub ON s.subject_id = sub.id
            WHERE {where}
            ORDER BY s.start_time DESC
        """, params)
        rows = [dict(r) for r in rows]

        import csv
        import io
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                row_clean = {}
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row_clean[k] = v.isoformat()
                    else:
                        row_clean[k] = v
                writer.writerow(row_clean)

        return {"csv": output.getvalue(), "count": len(rows)}
    except Exception as e:
        logger.error(f"导出失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        mysql.disconnect()
