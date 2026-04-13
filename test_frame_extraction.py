#!/usr/bin/env python3
"""
视频帧提取服务 - 单元测试和集成测试
"""

import unittest
import tempfile
import os
import json
import base64
from unittest.mock import patch, MagicMock
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from frame_extraction_service import app, FrameExtractionError


class TestFrameExtractionService(unittest.TestCase):
    """视频帧提取服务测试类"""
    
    def setUp(self):
        """测试前设置"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
    
    def test_metrics_endpoint(self):
        """测试指标端点"""
        response = self.app.get('/metrics')
        self.assertEqual(response.status_code, 200)
        self.assertTrue('frame_extraction_requests_total' in response.data.decode())
    
    def test_stats_endpoint(self):
        """测试统计端点"""
        response = self.app.get('/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['service'], 'frame_extraction_service')
    
    @patch('frame_extraction_service._download')
    @patch('frame_extraction_service._extract_frames')
    def test_json_request_success(self, mock_extract, mock_download):
        """测试JSON请求成功"""
        # 模拟帧提取结果
        mock_extract.return_value = {
            'frames': [
                {
                    'frame_index': 0,
                    'timestamp_seconds': 0.0,
                    'timestamp_formatted': '00:00:00.00',
                    'image_base64': 'test_base64',
                    'image_mime': 'image/jpeg'
                }
            ],
            'duration': 10.0
        }
        
        # 模拟下载成功
        mock_download.return_value = None
        
        # 发送JSON请求
        data = {
            'video_url': 'http://example.com/video.mp4',
            'max_frames': 5,
            'filename': 'test.mp4',
            'mime_type': 'video/mp4'
        }
        
        response = self.app.post('/extract', 
                                data=json.dumps(data),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result['success'])
        self.assertEqual(len(result['frames']), 1)
    
    def test_json_request_missing_url(self):
        """测试缺少视频URL的JSON请求"""
        data = {
            'max_frames': 5
        }
        
        response = self.app.post('/extract',
                                data=json.dumps(data),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.data)
        self.assertFalse(result['success'])
        self.assertEqual(result['error']['error_code'], 'MISSING_VIDEO_URL')
    
    def test_invalid_max_frames(self):
        """测试无效的帧数参数"""
        data = {
            'video_url': 'http://example.com/video.mp4',
            'max_frames': 200  # 超过最大值
        }
        
        response = self.app.post('/extract',
                                data=json.dumps(data),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.data)
        self.assertFalse(result['success'])
    
    def test_unsupported_format(self):
        """测试不支持的视频格式"""
        data = {
            'video_url': 'http://example.com/video.xyz',
            'max_frames': 5
        }
        
        response = self.app.post('/extract',
                                data=json.dumps(data),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.data)
        self.assertFalse(result['success'])
        self.assertEqual(result['error']['error_code'], 'UNSUPPORTED_FORMAT')


class TestFrameExtractionNode(unittest.TestCase):
    """Dify节点测试类"""
    
    def test_find_video(self):
        """测试视频文件查找"""
        from frame_extraction_node import _find_video, _get_field
        
        # 模拟Dify文件对象
        video_file = {
            'filename': 'test.mp4',
            'mime_type': 'video/mp4',
            'url': 'http://example.com/video.mp4'
        }
        
        text_file = {
            'filename': 'test.txt',
            'mime_type': 'text/plain',
            'url': 'http://example.com/text.txt'
        }
        
        files = [text_file, video_file]
        result = _find_video(files)
        self.assertEqual(result, video_file)
    
    def test_get_url_priority(self):
        """测试URL获取优先级"""
        from frame_extraction_node import _get_url
        
        # 测试out_url优先
        file_with_out_url = {
            'out_url': 'http://cos.example.com/video.mp4',
            'url': 'http://internal.example.com/video.mp4'
        }
        
        url = _get_url(file_with_out_url)
        self.assertEqual(url, 'http://cos.example.com/video.mp4')
    
    @patch('frame_extraction_node._http_post')
    def test_main_success(self, mock_post):
        """测试主函数成功"""
        from frame_extraction_node import main
        
        # 模拟服务响应
        mock_post.return_value = {
            'frames': [
                {
                    'frame_index': 0,
                    'timestamp_seconds': 0.0,
                    'timestamp_formatted': '00:00:00.00',
                    'image_base64': 'test_base64',
                    'image_mime': 'image/jpeg'
                }
            ],
            'video_duration': 10.0,
            'total_frames_extracted': 1,
            'error': None
        }
        
        # 模拟Dify文件数组
        files = [{
            'filename': 'test.mp4',
            'mime_type': 'video/mp4',
            'out_url': 'http://example.com/video.mp4'
        }]
        
        result = main(files, max_frames=5)
        self.assertIsNone(result['error'])
        self.assertEqual(len(result['frames']), 1)


class TestErrorHandling(unittest.TestCase):
    """错误处理测试类"""
    
    def test_frame_extraction_error(self):
        """测试自定义错误类"""
        error = FrameExtractionError('test_stage', 'TEST_ERROR', 'Test message', 400)
        self.assertEqual(error.stage, 'test_stage')
        self.assertEqual(error.code, 'TEST_ERROR')
        self.assertEqual(error.message, 'Test message')
        self.assertEqual(error.status_code, 400)
    
    def test_error_response_format(self):
        """测试错误响应格式"""
        from frame_extraction_service import _error
        
        error_response = _error('test', 'ERROR', 'Test error')
        self.assertFalse(error_response['success'])
        self.assertEqual(error_response['error']['error_code'], 'ERROR')


class TestPerformanceOptimization(unittest.TestCase):
    """性能优化测试类"""
    
    @patch('frame_extraction_service.psutil.Process')
    def test_memory_check(self, mock_process):
        """测试内存检查"""
        from frame_extraction_service import _check_memory_usage
        
        # 模拟低内存使用
        mock_memory = MagicMock()
        mock_memory.rss = 100 * 1024 * 1024  # 100MB
        mock_process.return_value.memory_info.return_value = mock_memory
        
        result = _check_memory_usage()
        self.assertTrue(result)
        
        # 模拟高内存使用
        mock_memory.rss = 600 * 1024 * 1024  # 600MB
        result = _check_memory_usage()
        self.assertFalse(result)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)