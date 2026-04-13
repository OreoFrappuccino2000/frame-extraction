#!/usr/bin/env python3
"""
腾讯云SCF处理函数 - 视频帧提取服务
"""

import json
import base64
import os
import sys
import tempfile
from frame_extraction_service import app


def main_handler(event, context):
    """
    SCF主处理函数
    """
    try:
        # 解析API网关事件
        if 'requestContext' in event:
            # API网关事件格式
            return _handle_api_gateway_event(event)
        else:
            # 直接调用事件格式
            return _handle_direct_event(event)
    except Exception as e:
        return {
            "isBase64Encoded": False,
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": False,
                "error": {
                    "error_stage": "scf_handler",
                    "error_code": "HANDLER_ERROR",
                    "error_message": str(e)
                }
            })
        }


def _handle_api_gateway_event(event):
    """处理API网关事件"""
    # 提取HTTP方法、路径和查询参数
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    # 构建WSGI环境
    environ = {
        'REQUEST_METHOD': http_method,
        'PATH_INFO': path,
        'QUERY_STRING': event.get('queryString', ''),
        'SERVER_NAME': 'scf.tencentcloudapi.com',
        'SERVER_PORT': '80',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https',
        'wsgi.input': None,
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }
    
    # 处理请求体
    body = event.get('body', '')
    if body:
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)
        environ['CONTENT_LENGTH'] = str(len(body))
        environ['wsgi.input'] = BytesIO(body)
    
    # 添加HTTP头
    headers = event.get('headers', {})
    for key, value in headers.items():
        header_name = 'HTTP_' + key.upper().replace('-', '_')
        environ[header_name] = value
    
    # 调用Flask应用
    response = app(environ, lambda *args: None)
    
    # 解析Flask响应
    status_code = response.status_code
    response_headers = dict(response.headers)
    response_body = response.get_data()
    
    return {
        "isBase64Encoded": False,
        "statusCode": status_code,
        "headers": response_headers,
        "body": response_body.decode('utf-8') if isinstance(response_body, bytes) else response_body
    }


def _handle_direct_event(event):
    """处理直接调用事件"""
    # 这里可以处理直接的事件调用（非HTTP）
    return {
        "success": False,
        "error": {
            "error_stage": "scf_handler",
            "error_code": "UNSUPPORTED_EVENT",
            "error_message": "Direct event calls are not supported. Use API Gateway."
        }
    }


class BytesIO:
    """模拟BytesIO对象"""
    def __init__(self, data):
        self.data = data
        self.pos = 0
    
    def read(self, size=-1):
        if size == -1:
            result = self.data[self.pos:]
            self.pos = len(self.data)
        else:
            result = self.data[self.pos:self.pos + size]
            self.pos += len(result)
        return result