-- MySQL dump 10.13  Distrib 8.0.44, for Linux (x86_64)
--
-- Host: localhost    Database: knowledge_graph_system
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `knowledge_graphs`
--

DROP TABLE IF EXISTS `knowledge_graphs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge_graphs` (
  `graph_id` varchar(36) NOT NULL COMMENT 'å›¾è°±å”¯ä¸€æ ‡è¯†UUID',
  `graph_name` varchar(255) NOT NULL COMMENT 'å›¾è°±åç§°',
  `description` text COMMENT 'å›¾è°±æè¿°',
  `data_source` varchar(255) DEFAULT NULL COMMENT 'æ•°æ®æ¥æº',
  `file_path` varchar(255) DEFAULT NULL COMMENT 'åŽŸå§‹æ–‡ä»¶è·¯å¾„',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'åˆ›å»ºæ—¶é—´',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'æ›´æ–°æ—¶é—´',
  `status` enum('pending','processing','completed','failed') DEFAULT 'pending' COMMENT 'å›¾è°±çŠ¶æ€',
  `entity_count` int DEFAULT '0' COMMENT 'å®žä½“æ•°é‡',
  `relation_count` int DEFAULT '0' COMMENT 'å…³ç³»æ•°é‡',
  `user_id` varchar(36) DEFAULT NULL COMMENT 'åˆ›å»ºè€…ID',
  `tags` varchar(255) DEFAULT NULL COMMENT 'æ ‡ç­¾ï¼Œé€—å·åˆ†éš”',
  PRIMARY KEY (`graph_id`),
  KEY `idx_graphs_status` (`status`),
  KEY `idx_graphs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='çŸ¥è¯†å›¾è°±å…ƒæ•°æ®';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `knowledge_graphs`
--
-- WHERE:  graph_id='5c716837-505e-41b5-b2db-5b6fdf3c0ea7'

LOCK TABLES `knowledge_graphs` WRITE;
/*!40000 ALTER TABLE `knowledge_graphs` DISABLE KEYS */;
/*!40000 ALTER TABLE `knowledge_graphs` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-02-11 13:18:52
