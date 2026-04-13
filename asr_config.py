"""
ASR服务配置文件
管理各种ASR服务的API密钥和配置
"""

import os
from typing import Dict, Any

# ASR服务配置类
class ASRConfig:
    """ASR服务配置管理"""
    
    # 腾讯云ASR配置
    TENCENT_CONFIG = {
        "enabled": False,  # 是否启用腾讯云ASR
        "secret_id": os.getenv("TENCENT_SECRET_ID", ""),
        "secret_key": os.getenv("TENCENT_SECRET_KEY", ""),
        "region": "ap-beijing",  # 区域
        "engine_model_type": "16k_zh",  # 引擎模型类型
        "endpoint": "https://asr.tencentcloudapi.com"
    }
    
    # Google Speech-to-Text配置
    GOOGLE_CONFIG = {
        "enabled": False,  # 是否启用Google ASR
        "credentials_file": os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
        "language_codes": {
            "zh": "zh-CN",
            "en": "en-US", 
            "ja": "ja-JP",
            "ko": "ko-KR"
        }
    }
    
    # 百度AI ASR配置
    BAIDU_CONFIG = {
        "enabled": False,  # 是否启用百度ASR
        "app_id": os.getenv("BAIDU_ASR_APP_ID", ""),
        "api_key": os.getenv("BAIDU_ASR_API_KEY", ""),
        "secret_key": os.getenv("BAIDU_ASR_SECRET_KEY", ""),
        "language_codes": {
            "zh": "1537",  # 普通话
            "en": "1737"   # 英语
        }
    }
    
    # 阿里云ASR配置
    ALIYUN_CONFIG = {
        "enabled": False,  # 是否启用阿里云ASR
        "access_key_id": os.getenv("ALIYUN_ACCESS_KEY_ID", ""),
        "access_key_secret": os.getenv("ALIYUN_ACCESS_KEY_SECRET", ""),
        "region": "cn-shanghai",
        "app_key": os.getenv("ALIYUN_ASR_APP_KEY", "")
    }
    
    # 默认配置
    DEFAULT_CONFIG = {
        "primary_service": "mock",  # 默认使用模拟服务
        "fallback_service": "mock",  # 备用服务
        "timeout": 30,  # 超时时间(秒)
        "max_retries": 3,  # 最大重试次数
        "similarity_threshold": 0.7,  # 相似度阈值
        "confidence_threshold": 0.5   # 置信度阈值
    }
    
    @classmethod
    def get_service_config(cls, service_name: str) -> Dict[str, Any]:
        """获取指定ASR服务的配置"""
        configs = {
            "tencent": cls.TENCENT_CONFIG,
            "google": cls.GOOGLE_CONFIG,
            "baidu": cls.BAIDU_CONFIG,
            "aliyun": cls.ALIYUN_CONFIG
        }
        return configs.get(service_name, {})
    
    @classmethod
    def is_service_enabled(cls, service_name: str) -> bool:
        """检查ASR服务是否启用"""
        config = cls.get_service_config(service_name)
        return config.get("enabled", False)
    
    @classmethod
    def get_available_services(cls) -> list:
        """获取可用的ASR服务列表"""
        available = []
        for service in ["tencent", "google", "baidu", "aliyun"]:
            if cls.is_service_enabled(service):
                available.append(service)
        return available if available else ["mock"]  # 如果没有可用服务，返回模拟服务
    
    @classmethod
    def get_best_service_for_language(cls, language: str) -> str:
        """根据语言选择最佳的ASR服务"""
        # 服务优先级：腾讯云(中文) > Google(多语言) > 百度(中文) > 阿里云(中文)
        
        if language == "zh":
            # 中文优先选择腾讯云或百度
            if cls.is_service_enabled("tencent"):
                return "tencent"
            elif cls.is_service_enabled("baidu"):
                return "baidu"
            elif cls.is_service_enabled("aliyun"):
                return "aliyun"
        
        # 其他语言或没有中文服务时选择Google
        if cls.is_service_enabled("google"):
            return "google"
        
        # 如果没有可用服务，使用模拟服务
        return "mock"
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """验证配置完整性"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "available_services": cls.get_available_services()
        }
        
        # 检查各服务的配置
        for service_name in ["tencent", "google", "baidu", "aliyun"]:
            config = cls.get_service_config(service_name)
            if config.get("enabled", False):
                # 检查必要的配置项
                if service_name == "tencent":
                    if not config.get("secret_id") or not config.get("secret_key"):
                        validation_result["errors"].append(f"{service_name}: 缺少Secret ID或Secret Key")
                elif service_name == "google":
                    if not config.get("credentials_file"):
                        validation_result["warnings"].append(f"{service_name}: 未配置凭证文件")
                elif service_name == "baidu":
                    if not all([config.get("app_id"), config.get("api_key"), config.get("secret_key")]):
                        validation_result["errors"].append(f"{service_name}: 缺少App ID、API Key或Secret Key")
                elif service_name == "aliyun":
                    if not all([config.get("access_key_id"), config.get("access_key_secret")]):
                        validation_result["errors"].append(f"{service_name}: 缺少Access Key ID或Secret")
        
        if validation_result["errors"]:
            validation_result["valid"] = False
        
        return validation_result

# 环境变量配置示例
ENV_VARIABLES = {
    "TENCENT_SECRET_ID": "腾讯云Secret ID",
    "TENCENT_SECRET_KEY": "腾讯云Secret Key",
    "GOOGLE_APPLICATION_CREDENTIALS": "Google服务账号JSON文件路径",
    "BAIDU_ASR_APP_ID": "百度ASR App ID",
    "BAIDU_ASR_API_KEY": "百度ASR API Key",
    "BAIDU_ASR_SECRET_KEY": "百度ASR Secret Key",
    "ALIYUN_ACCESS_KEY_ID": "阿里云Access Key ID",
    "ALIYUN_ACCESS_KEY_SECRET": "阿里云Access Key Secret",
    "ALIYUN_ASR_APP_KEY": "阿里云ASR App Key"
}

# 使用示例
if __name__ == "__main__":
    # 验证配置
    validation = ASRConfig.validate_config()
    print("配置验证结果:")
    print(f"有效: {validation['valid']}")
    print(f"可用服务: {validation['available_services']}")
    print(f"错误: {validation['errors']}")
    print(f"警告: {validation['warnings']}")
    
    # 测试语言选择
    languages = ["zh", "en", "ja", "ko"]
    for lang in languages:
        best_service = ASRConfig.get_best_service_for_language(lang)
        print(f"语言 '{lang}' 的最佳服务: {best_service}")