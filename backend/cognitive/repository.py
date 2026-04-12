#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据仓储层
认知负荷评估数据的持久化操作

基于SQLAlchemy版MySQLClient实现
"""

import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy import text

from db.mysql_client import MySQLClient
from loguru import logger


class CognitiveLoadRepository:
    """
    认知负荷数据仓储层

    职责：
    1. 评估记录CRUD
    2. 行为事件存储
    3. NASA-TLX答案存储
    4. 评估报告存储
    5. 用户认知画像更新
    6. 趋势分析查询
    """

    def __init__(self):
        self.mysql = MySQLClient()
        self.mysql.connect()
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """确保所需表已创建"""
        try:
            self.mysql.execute_update("""
            CREATE TABLE IF NOT EXISTS cognitive_load_assessment (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(64),
                agent_session_id VARCHAR(64),
                task_id VARCHAR(128) NOT NULL,
                source VARCHAR(32) NOT NULL,
                task_start_ts BIGINT,
                task_end_ts BIGINT,
                duration_ms BIGINT,
                final_score DECIMAL(5,4) NOT NULL,
                level VARCHAR(16) NOT NULL,
                behavior_score DECIMAL(5,4),
                questionnaire_score DECIMAL(5,4),
                eeg_score DECIMAL(5,4),
                behavior_features JSON,
                questionnaire_features JSON,
                eeg_features JSON,
                fusion_method VARCHAR(32) DEFAULT 'weighted',
                available_modalities VARCHAR(64),
                modality_weights JSON,
                recommendations JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_session (user_id, session_id),
                INDEX idx_user_created (user_id, created_at),
                INDEX idx_task_source (task_id, source),
                INDEX idx_level (level),
                INDEX idx_final_score (final_score),
                INDEX idx_agent_session (agent_session_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='认知负荷评估记录主表'
            """)

            self.mysql.execute_update("""
            CREATE TABLE IF NOT EXISTS cognitive_behavior_events (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(64),
                task_id VARCHAR(128) NOT NULL,
                source VARCHAR(32) NOT NULL,
                event_type VARCHAR(32) NOT NULL,
                ts BIGINT NOT NULL,
                params JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_session (session_id),
                INDEX idx_task (task_id),
                INDEX idx_event_type (event_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='认知负荷行为事件原始记录表'
            """)

            self.mysql.execute_update("""
            CREATE TABLE IF NOT EXISTS cognitive_nasa_tlx_answers (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                assessment_id BIGINT NOT NULL,
                user_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(64),
                task_id VARCHAR(128) NOT NULL,
                source VARCHAR(32) NOT NULL,
                mental_demand INT NOT NULL,
                physical_demand INT NOT NULL,
                temporal_demand INT NOT NULL,
                performance INT NOT NULL,
                effort INT NOT NULL,
                frustration INT NOT NULL,
                weighted_score DECIMAL(5,4),
                submitted_at BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_assessment (assessment_id),
                INDEX idx_user_session (user_id, session_id),
                UNIQUE KEY uk_assessment (assessment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='NASA-TLX问卷答案表(6维度)'
            """)

            self.mysql.execute_update("""
            CREATE TABLE IF NOT EXISTS cognitive_load_report (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                assessment_id BIGINT NOT NULL,
                user_id VARCHAR(64) NOT NULL,
                report_type VARCHAR(32) NOT NULL,
                summary JSON,
                radar_chart JSON,
                trend_analysis JSON,
                suggestions JSON,
                benchmarks JSON,
                generated_by VARCHAR(32) DEFAULT 'system',
                model_version VARCHAR(32),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_assessment (assessment_id),
                INDEX idx_user (user_id),
                INDEX idx_report_type (report_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='认知负荷评估报告表'
            """)

            self.mysql.execute_update("""
            CREATE TABLE IF NOT EXISTS cognitive_eeg_features (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                assessment_id BIGINT NOT NULL,
                user_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(64),
                device_type VARCHAR(32),
                sampling_rate INT,
                alpha_power DECIMAL(10,6),
                beta_power DECIMAL(10,6),
                theta_power DECIMAL(10,6),
                delta_power DECIMAL(10,6),
                alpha_beta_ratio DECIMAL(8,4),
                theta_beta_ratio DECIMAL(8,4),
                frontal_asymmetry DECIMAL(8,4),
                signal_quality DECIMAL(3,2),
                artifact_rejected BOOLEAN DEFAULT FALSE,
                recording_duration_ms BIGINT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_assessment (assessment_id),
                INDEX idx_user_session (user_id, session_id),
                INDEX idx_recorded_at (recorded_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='EEG特征数据表(预留)'
            """)

            logger.info("认知负荷相关表创建/检查完成")

        except Exception as e:
            logger.error(f"创建认知负荷表失败: {e}")

    def save_assessment(self, assessment_data: Dict[str, Any]) -> int:
        """
        保存评估记录

        Args:
            assessment_data: 评估数据字典

        Returns:
            assessment_id: 新增记录的ID
        """
        try:
            behavior_features_json = None
            if assessment_data.get("behavior_features"):
                bf = assessment_data["behavior_features"]
                if hasattr(bf, 'model_dump'):
                    behavior_features_json = json.dumps(bf.model_dump(), ensure_ascii=False)
                else:
                    behavior_features_json = json.dumps(bf, ensure_ascii=False)

            questionnaire_features_json = None
            if assessment_data.get("questionnaire_features"):
                qf = assessment_data["questionnaire_features"]
                if hasattr(qf, 'model_dump'):
                    questionnaire_features_json = json.dumps(qf.model_dump(), ensure_ascii=False)
                else:
                    questionnaire_features_json = json.dumps(qf, ensure_ascii=False)

            eeg_features_json = None
            if assessment_data.get("eeg_features"):
                ef = assessment_data["eeg_features"]
                if hasattr(ef, 'model_dump'):
                    eeg_features_json = json.dumps(ef.model_dump(), ensure_ascii=False)
                else:
                    eeg_features_json = json.dumps(ef, ensure_ascii=False)

            modality_weights_json = None
            if assessment_data.get("modality_weights"):
                modality_weights_json = json.dumps(assessment_data["modality_weights"], ensure_ascii=False)

            recommendations_json = None
            if assessment_data.get("recommendations"):
                recommendations_json = json.dumps(assessment_data["recommendations"], ensure_ascii=False)

            available_modalities = assessment_data.get("available_modalities", [])
            if isinstance(available_modalities, list):
                available_modalities = ",".join(available_modalities)

            result = self.mysql.execute_update("""
            INSERT INTO cognitive_load_assessment (
                user_id, session_id, agent_session_id, task_id, source,
                task_start_ts, task_end_ts, duration_ms,
                final_score, level,
                behavior_score, questionnaire_score, eeg_score,
                behavior_features, questionnaire_features, eeg_features,
                fusion_method, available_modalities, modality_weights, recommendations
            ) VALUES (
                :user_id, :session_id, :agent_session_id, :task_id, :source,
                :task_start_ts, :task_end_ts, :duration_ms,
                :final_score, :level,
                :behavior_score, :questionnaire_score, :eeg_score,
                :behavior_features, :questionnaire_features, :eeg_features,
                :fusion_method, :available_modalities, :modality_weights, :recommendations
            )
            """, {
                "user_id": assessment_data.get("user_id"),
                "session_id": assessment_data.get("session_id"),
                "agent_session_id": assessment_data.get("agent_session_id"),
                "task_id": assessment_data.get("task_id"),
                "source": assessment_data.get("source"),
                "task_start_ts": assessment_data.get("task_start_ts"),
                "task_end_ts": assessment_data.get("task_end_ts"),
                "duration_ms": assessment_data.get("duration_ms"),
                "final_score": assessment_data.get("final_score"),
                "level": assessment_data.get("level"),
                "behavior_score": assessment_data.get("behavior_score"),
                "questionnaire_score": assessment_data.get("questionnaire_score"),
                "eeg_score": assessment_data.get("eeg_score"),
                "behavior_features": behavior_features_json,
                "questionnaire_features": questionnaire_features_json,
                "eeg_features": eeg_features_json,
                "fusion_method": assessment_data.get("fusion_method", "weighted"),
                "available_modalities": available_modalities,
                "modality_weights": modality_weights_json,
                "recommendations": recommendations_json
            })

            assessment_id = self._get_last_insert_id()

            if assessment_data.get("behavior_events"):
                self._save_behavior_events(
                    assessment_data["user_id"],
                    assessment_data.get("session_id"),
                    assessment_data["task_id"],
                    assessment_data.get("source"),
                    assessment_data["behavior_events"]
                )

            if assessment_data.get("nasa_tlx_answers"):
                self._save_nasa_tlx_answers(
                    assessment_id,
                    assessment_data["user_id"],
                    assessment_data.get("session_id"),
                    assessment_data["task_id"],
                    assessment_data.get("source"),
                    assessment_data["nasa_tlx_answers"],
                    assessment_data.get("questionnaire_score")
                )

            logger.info(f"评估记录保存成功: assessment_id={assessment_id}")
            return assessment_id

        except Exception as e:
            logger.error(f"保存评估记录失败: {e}")
            raise

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        result = self.mysql.execute_query("SELECT LAST_INSERT_ID() as id")
        if result:
            return result[0].get('id', 0)
        return 0

    def save_eeg_features(self, assessment_id: int, user_id: str, eeg_data: Dict[str, Any], session_id: Optional[str] = None) -> bool:
        """保存EEG特征数据"""
        try:
            self.mysql.execute_update("""
            INSERT INTO cognitive_eeg_features (
                assessment_id, user_id, session_id, device_type, sampling_rate,
                alpha_power, beta_power, theta_power, delta_power,
                alpha_beta_ratio, theta_beta_ratio, frontal_asymmetry,
                signal_quality, artifact_rejected, recording_duration_ms
            ) VALUES (
                :assessment_id, :user_id, :session_id, :device_type, :sampling_rate,
                :alpha_power, :beta_power, :theta_power, :delta_power,
                :alpha_beta_ratio, :theta_beta_ratio, :frontal_asymmetry,
                :signal_quality, :artifact_rejected, :recording_duration_ms
            )
            """, {
                "assessment_id": assessment_id,
                "user_id": user_id,
                "session_id": session_id,
                "device_type": eeg_data.get("device_type"),
                "sampling_rate": eeg_data.get("sampling_rate"),
                "alpha_power": eeg_data.get("alpha_power"),
                "beta_power": eeg_data.get("beta_power"),
                "theta_power": eeg_data.get("theta_power"),
                "delta_power": eeg_data.get("delta_power"),
                "alpha_beta_ratio": eeg_data.get("alpha_beta_ratio"),
                "theta_beta_ratio": eeg_data.get("theta_beta_ratio"),
                "frontal_asymmetry": eeg_data.get("frontal_asymmetry"),
                "signal_quality": eeg_data.get("signal_quality", 0.5),
                "artifact_rejected": eeg_data.get("artifact_rejected", False),
                "recording_duration_ms": eeg_data.get("recording_duration_ms")
            })
            logger.info(f"EEG特征保存成功: assessment_id={assessment_id}")
            return True
        except Exception as e:
            logger.error(f"保存EEG特征失败: {e}")
            return False

    def _save_behavior_events(
        self,
        user_id: str,
        session_id: Optional[str],
        task_id: str,
        source: str,
        events: List[Dict]
    ) -> None:
        """保存行为事件"""
        for event in events:
            params_json = json.dumps(event.get("params", {}), ensure_ascii=False) if event.get("params") else None
            self.mysql.execute_update("""
            INSERT INTO cognitive_behavior_events (
                user_id, session_id, task_id, source, event_type, ts, params
            ) VALUES (:user_id, :session_id, :task_id, :source, :event_type, :ts, :params)
            """, {
                "user_id": user_id,
                "session_id": session_id,
                "task_id": task_id,
                "source": source,
                "event_type": event.get("event_type"),
                "ts": event.get("ts"),
                "params": params_json
            })

    def _save_nasa_tlx_answers(
        self,
        assessment_id: int,
        user_id: str,
        session_id: Optional[str],
        task_id: str,
        source: str,
        answers: Dict,
        weighted_score: Optional[float]
    ) -> None:
        """保存NASA-TLX答案"""
        mental = answers.get("mental_demand", 4)
        physical = answers.get("physical_demand", 4)
        temporal = answers.get("temporal_demand", 4)
        performance = answers.get("performance", 4)
        effort = answers.get("effort", 4)
        frustration = answers.get("frustration", 4)

        submitted_at = answers.get("submitted_at", int(datetime.now().timestamp() * 1000))

        self.mysql.execute_update("""
        INSERT INTO cognitive_nasa_tlx_answers (
            assessment_id, user_id, session_id, task_id, source,
            mental_demand, physical_demand, temporal_demand,
            performance, effort, frustration,
            weighted_score, submitted_at
        ) VALUES (
            :assessment_id, :user_id, :session_id, :task_id, :source,
            :mental, :physical, :temporal, :performance, :effort, :frustration,
            :weighted_score, :submitted_at
        )
        """, {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "session_id": session_id,
            "task_id": task_id,
            "source": source,
            "mental": mental,
            "physical": physical,
            "temporal": temporal,
            "performance": performance,
            "effort": effort,
            "frustration": frustration,
            "weighted_score": weighted_score,
            "submitted_at": submitted_at
        })

    def get_assessment(self, assessment_id: int) -> Optional[Dict]:
        """获取单条评估记录"""
        results = self.mysql.execute_query(
            "SELECT * FROM cognitive_load_assessment WHERE id = :id",
            {"id": assessment_id}
        )
        if results and len(results) > 0:
            return self._parse_assessment_row(results[0])
        return None

    def get_user_assessments(
        self,
        user_id: str,
        source: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """获取用户的评估历史"""
        query = "SELECT * FROM cognitive_load_assessment WHERE user_id = :user_id"
        params = {"user_id": user_id}

        if source:
            query += " AND source = :source"
            params["source"] = source

        if days:
            query += " AND created_at >= DATE_SUB(NOW(), INTERVAL :days DAY)"
            params["days"] = days

        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        results = self.mysql.execute_query(query, params)
        return [self._parse_assessment_row(row) for row in results]

    def _parse_assessment_row(self, result) -> Dict:
        """解析评估记录行"""
        if not result:
            return result

        # RowMapping 不支持原地赋值，统一转为普通 dict
        result = dict(result)

        for field in ["behavior_features", "questionnaire_features", "eeg_features",
                       "modality_weights", "recommendations"]:
            if result.get(field) and isinstance(result[field], str):
                try:
                    result[field] = json.loads(result[field])
                except:
                    pass

        if result.get("created_at"):
            result["created_at"] = result["created_at"].isoformat() if hasattr(result["created_at"], 'isoformat') else str(result["created_at"])

        return result

    def get_nasa_tlx_answers(self, assessment_id: int) -> Optional[Dict]:
        """获取NASA-TLX答案"""
        results = self.mysql.execute_query(
            "SELECT * FROM cognitive_nasa_tlx_answers WHERE assessment_id = :id",
            {"id": assessment_id}
        )
        if results and len(results) > 0:
            row = results[0]
            return {
                "mental_demand": row["mental_demand"],
                "physical_demand": row["physical_demand"],
                "temporal_demand": row["temporal_demand"],
                "performance": row["performance"],
                "effort": row["effort"],
                "frustration": row["frustration"],
                "weighted_score": row.get("weighted_score"),
                "submitted_at": row.get("submitted_at")
            }
        return None

    def get_trend_analysis(
        self,
        user_id: str,
        days: int = 7,
        source: Optional[str] = None
    ) -> Dict:
        """获取认知负荷趋势分析"""
        assessments = self.get_user_assessments(user_id, source, days, 1000)

        if not assessments:
            return {
                "dates": [],
                "scores": [],
                "levels": [],
                "nasa_tlx_trends": {},
                "summary": {
                    "avg_score": 0,
                    "total_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0
                }
            }

        dates = []
        scores = []
        levels = []

        for a in assessments:
            created_at = a.get("created_at", "")
            if "T" in created_at:
                date_str = created_at.split("T")[0]
            else:
                date_str = str(created_at)[:10]
            dates.append(date_str)
            scores.append(a.get("final_score", 0))
            levels.append(a.get("level", "unknown"))

        high_count = sum(1 for l in levels if l == "high")
        medium_count = sum(1 for l in levels if l == "medium")
        low_count = sum(1 for l in levels if l == "low")

        return {
            "dates": dates,
            "scores": scores,
            "levels": levels,
            "nasa_tlx_trends": {},
            "summary": {
                "avg_score": sum(scores) / len(scores) if scores else 0,
                "total_count": len(assessments),
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count
            }
        }

    def get_user_stats(self, user_id: str) -> Dict:
        """获取用户认知负荷统计"""
        assessments = self.get_user_assessments(user_id, None, None, 1000)

        if not assessments:
            return {
                "total": 0,
                "avg_score": 0,
                "min_score": 0,
                "max_score": 0,
                "level_distribution": {"high": 0, "medium": 0, "low": 0}
            }

        scores = [a.get("final_score", 0) for a in assessments]
        levels = [a.get("level", "unknown") for a in assessments]

        return {
            "total": len(assessments),
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "level_distribution": {
                "high": sum(1 for l in levels if l == "high"),
                "medium": sum(1 for l in levels if l == "medium"),
                "low": sum(1 for l in levels if l == "low")
            }
        }

    def get_modality_status(self) -> Dict:
        """获取各模态状态"""
        return {
            "behavior": {"available": True, "weight": 0.4},
            "questionnaire": {"available": True, "weight": 0.6},
            "eeg": {"available": False, "weight": 0.0, "note": "等待EEG设备接入"}
        }

    def cache_assessment_session(self, session_id: str, partial_data: Dict, ttl: int = 3600) -> bool:
        """缓存评估会话中间状态"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
            cache_key = f"cognitive_session:{session_id}"
            r.setex(cache_key, ttl, json.dumps(partial_data, ensure_ascii=False))
            logger.debug(f"会话缓存成功: {session_id}")
            return True
        except Exception as e:
            logger.warning(f"会话缓存失败: {e}")
            return False

    def get_cached_session(self, session_id: str) -> Optional[Dict]:
        """获取缓存的评估会话"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
            cache_key = f"cognitive_session:{session_id}"
            data = r.get(cache_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"获取缓存会话失败: {e}")
            return None

    def delete_cached_session(self, session_id: str) -> bool:
        """删除缓存的评估会话"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
            cache_key = f"cognitive_session:{session_id}"
            r.delete(cache_key)
            return True
        except Exception as e:
            logger.warning(f"删除缓存会话失败: {e}")
            return False


_repository_instance = None

def get_cognitive_repository() -> CognitiveLoadRepository:
    """获取仓储单例"""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = CognitiveLoadRepository()
    return _repository_instance
