import logging
import jwt
import asyncio
import os
import socket
import sys
from astrbot.core.config.default import VERSION
from quart import Quart, request, jsonify, g
from quart.logging import default_handler
from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
from .routes import *
from .routes.route import RouteContext, Response
from astrbot.core import logger, WEBUI_SK
from astrbot.core.db import BaseDatabase
from astrbot.core.utils.io import get_local_ip_addresses

DATAPATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data"))

class AstrBotDashboard():
    def __init__(self, core_lifecycle: AstrBotCoreLifecycle, db: BaseDatabase) -> None:
        self.core_lifecycle = core_lifecycle
        self.config = core_lifecycle.astrbot_config
        self.data_path = os.path.abspath(os.path.join(DATAPATH, "dist"))
        self.app = Quart("dashboard", static_folder=self.data_path, static_url_path="/")
        self.app.json.sort_keys = False
        self.app.before_request(self.auth_middleware)
        # token 用于验证请求
        logging.getLogger(self.app.name).removeHandler(default_handler)
        self.context = RouteContext(self.config, self.app)
        self.ur = UpdateRoute(self.context, core_lifecycle.astrbot_updator, core_lifecycle)
        self.sr = StatRoute(self.context, db, core_lifecycle)
        self.pr = PluginRoute(self.context, core_lifecycle, core_lifecycle.plugin_manager)
        self.cr = ConfigRoute(self.context, core_lifecycle)
        self.lr = LogRoute(self.context, core_lifecycle.log_broker)
        self.sfr = StaticFileRoute(self.context)
        self.ar = AuthRoute(self.context)
        self.chat_route = ChatRoute(self.context, db, core_lifecycle)
        
    async def auth_middleware(self):
        if not request.path.startswith("/api"):
            return
        if request.path == "/api/auth/login":
            return
        if request.path == "/api/chat/get_file":
            return
        # claim jwt
        token = request.headers.get("Authorization")
        if not token:
            r = jsonify(Response().error("未授权").__dict__)
            r.status_code = 401
            return r
        if token.startswith("Bearer "):
            token = token[7:]
        try:
            payload = jwt.decode(token, WEBUI_SK, algorithms=["HS256"])
            g.username = payload["username"]
        except jwt.ExpiredSignatureError:
            r = jsonify(Response().error("Token 过期").__dict__)
            r.status_code = 401
            return r
        except jwt.InvalidTokenError:
            r = jsonify(Response().error("Token 无效").__dict__)
            r.status_code = 401
            return r
        
        
    async def shutdown_trigger_placeholder(self):
        while not self.core_lifecycle.event_queue.closed:
            await asyncio.sleep(1)
        logger.info("管理面板已关闭。")
        
    def check_port_in_use(self, port: int) -> bool:
        """
        跨平台检测端口是否被占用
        """
        try:
            # 创建 IPv4 TCP Socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 设置超时时间
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            # result 为 0 表示端口被占用
            return result == 0
        except Exception as e:
            logger.warning(f"检查端口 {port} 时发生错误: {str(e)}")
            # 如果出现异常，保守起见认为端口可能被占用
            return True
    
    def run(self):
        try:
            ip_addr = get_local_ip_addresses()
        except Exception as e:
            ip_addr = []
            
        port = self.core_lifecycle.astrbot_config['dashboard'].get("port", 6185)
        if isinstance(port, str):
            port = int(port)

        if self.check_port_in_use(port):
            logger.error(f"错误：端口 {port} 已被占用，请确保：\n"
                        f"1. 没有其他 AstrBot 实例正在运行\n"
                        f"2. 端口 {port} 没有被其他程序占用\n"
                        f"3. 如需使用其他端口，请修改配置文件")
            
            raise Exception(f"端口 {port} 已被占用")
    
        display = f"\n ✨✨✨\n  AstrBot v{VERSION} 管理面板已启动，可访问\n\n"
        display += f"   ➜  本地: http://localhost:{port}\n"
        for ip in ip_addr:
            display += f"   ➜  网络: http://{ip}:{port}\n"
        display += "   ➜  默认用户名和密码: astrbot\n ✨✨✨\n"
        logger.info(display)
        

        return self.app.run_task(host="0.0.0.0", port=port, shutdown_trigger=self.shutdown_trigger_placeholder)