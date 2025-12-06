import jmcomic
from ncatbot.plugin_system import NcatBotPlugin, command_registry
from dataclasses import dataclass, field, is_dataclass, fields, MISSING
from ncatbot.utils import get_log
from ncatbot.core.event import GroupMessageEvent

PLUGIN_NAME = 'UnnamedJmComicIntegrate'

logger = get_log(PLUGIN_NAME)


# noinspection PyDataclass,PyArgumentList
def bind_config[T](plugin: NcatBotPlugin, config_class: type[T]) -> T:
    """
    将 Dataclass 绑定到 NcatBot 的配置系统 (Python 3.12+ PEP 695 版本)。
    """
    if not is_dataclass(config_class):
        raise TypeError("config_class must be a dataclass")
    # 1. 自动注册配置项
    for reg_field in fields(config_class):
        # === 修复核心：使用 MISSING 哨兵值进行判断 ===
        # 情况 A: 字段定义了 default (例如: a: int = 1)
        if reg_field.default is not MISSING:
            default_val = reg_field.default
        # 情况 B: 字段定义了 default_factory (例如: b: list = field(default_factory=list))
        elif reg_field.default_factory is not MISSING:
            default_val = reg_field.default_factory()
        # 情况 C: 没有默认值 (在配置系统中通常设为 None 或报错，这里给 None 方便注册)
        else:
            default_val = None
        # 注册到 NcatBot
        # 如果 data/xxx.yaml 中已经有值，NcatBot 会忽略这个 default_val
        plugin.register_config(reg_field.name, default_val, value_type=type(default_val))
    # 2. 从 plugin.config 读取最终值 (YAML > 默认值)
    loaded_data = {}
    for reg_field in fields(config_class):
        if reg_field.name in plugin.config:
            loaded_data[reg_field.name] = plugin.config[reg_field.name]
    # 3. 实例化 Dataclass
    return config_class(**loaded_data)


def format_name(raw_str) -> str:
    converted_str = ''
    in_bracket = 0
    for c in raw_str:
        if c in [']', '}', ')', '】', '）', '］']:
            in_bracket -= 1
            continue
        elif c in ['[', '{', '【', '(', '（', '［']:
            in_bracket += 1
            continue
        elif c == ' ':
            continue
        if not in_bracket:
            converted_str += c
        else:
            continue
    return converted_str


@dataclass
class JmComicConfig:
    proxy_server: str = field(default='')


class UnnamedJmComicIntegrate(NcatBotPlugin):
    name = PLUGIN_NAME  # 必须，插件名称，要求全局独立
    version = "0.0.1"  # 必须，插件版本
    dependencies = {}  # 必须，依赖的其他插件和版本
    description = "集成jmcomic功能"  # 可选
    author = "default_user"  # 可选

    jm_config: JmComicConfig = None
    jm_client: jmcomic.JmApiClient | jmcomic.JmHtmlClient = None

    async def on_load(self) -> None:
        jmcomic.disable_jm_log()
        jm_option = jmcomic.JmOption.default()
        self.jm_config = bind_config(self, JmComicConfig)
        if self.jm_config.proxy_server:
            logger.info(f'检测到已配置代理: {self.jm_config.proxy_server}')
            jm_option.client['postman']['meta_data']['proxies']['http'] = self.jm_config.proxy_server
        self.jm_client = jmcomic.JmOption.new_jm_client(jm_option)
        await super().on_load()

    @command_registry.command('jm')
    async def resolve_jmid(self, event: GroupMessageEvent, jm_id: int = -1) -> None:
        if jm_id == -1:
            await event.reply(f'未设定jmid,重试')
            return
        page = self.jm_client.search_site(search_query=str(jm_id))
        if not hasattr(page, 'album'):
            await event.reply(f'无法解析的JM号{jm_id}')
            return
        album: jmcomic.JmAlbumDetail = page.single_album
        await self.api.send_group_text(event.group_id, album.title)
        await event.reply(f'\n{album.title=}\n{album.tags}')

    async def on_close(self) -> None:
        await super().on_close()
