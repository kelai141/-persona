"""
AstrBot Persona Commands Plugin
复刻 /re-persona 指令，用于列出和切换人格

使用方法：
- /re-persona - 列出所有人格
- /re-persona <人格名> - 切换到指定人格
- /re-persona view <人格名> - 查看人格详细信息
"""
from typing import TYPE_CHECKING

from astrbot.api import star, logger
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Star

if TYPE_CHECKING:
    from astrbot.core.db.po import Persona


class PersonaPlugin(Star):
    """Persona 命令插件，复刻被移除的内置 persona 指令"""

    def __init__(self, context: star.Context):
        super().__init__(context)

    def _build_tree_output(
        self,
        folder_tree: list[dict],
        all_personas: list["Persona"],
        depth: int = 0,
    ) -> list[str]:
        """递归构建树状输出，使用短线条表示层级"""
        lines: list[str] = []
        for folder in folder_tree:
            lines.append(f"{'│ ' * depth}├ 📁 {folder['name']}/")
            folder_personas = [
                p for p in all_personas if p.folder_id == folder["folder_id"]
            ]
            child_prefix = "│ " * (depth + 1)
            for persona in folder_personas:
                lines.append(f"{child_prefix}├ 👤 {persona.persona_id}")
            children = folder.get("children", [])
            if children:
                lines.extend(
                    self._build_tree_output(
                        children,
                        all_personas,
                        depth + 1,
                    )
                )
        return lines

    @filter.command("re-persona")
    async def persona(self, event: AstrMessageEvent):
        """
        Persona 命令主入口

        使用方法：
        - /re-persona - 列出所有人格
        - /re-persona <人格名> - 切换到指定人格
        - /re-persona view <人格名> - 查看人格详细信息
        """
        message_str = event.message_str.strip()
        l = message_str.split(" ")
        umo = event.unified_msg_origin

        if len(l) == 1 or (len(l) == 2 and l[1] == ""):
            msg = (
                "📂 **人格管理**\n\n"
                "使用方法：\n"
                "• `/re-persona` - 列出所有人格\n"
                "• `/re-persona <人格名>` - 切换到指定人格\n"
                "• `/re-persona view <人格名>` - 查看人格详细信息\n"
                "\n输入 `/re-persona list` 查看所有可用人格。"
            )
            yield event.plain_result(msg)
            return

        if l[1] == "list":
            folder_tree = await self.context.persona_manager.get_folder_tree()
            all_personas = self.context.persona_manager.personas

            lines = ["📂 **人格列表：**\n"]
            tree_lines = self._build_tree_output(folder_tree, all_personas)
            lines.extend(tree_lines)

            root_personas = [p for p in all_personas if p.folder_id is None]
            if root_personas:
                if tree_lines:
                    lines.append("")
                for persona in root_personas:
                    lines.append(f"👤 {persona.persona_id}")

            total_count = len(all_personas)
            lines.append(f"\n共 {total_count} 个人格")
            lines.append("\n*使用 `/re-persona <人格名>` 设置人格")
            lines.append("*使用 `/re-persona view <人格名>` 查看详细信息")

            msg = "\n".join(lines)
            yield event.plain_result(msg)
            return

        if l[1] == "view":
            if len(l) == 2:
                yield event.plain_result("请输入人格情景名")
                return

            persona_name = " ".join(l[2:])
            personas = self.context.persona_manager.personas
            target_persona = None

            for p in personas:
                if p.persona_id == persona_name:
                    target_persona = p
                    break

            if not target_persona:
                yield event.plain_result(f"未找到人格：{persona_name}")
                return

            lines = [f"📋 **人格详情：{target_persona.persona_id}**\n"]
            system_prompt = target_persona.system_prompt or ""
            lines.append(f"系统提示词：\n{system_prompt[:200]}...")
            if target_persona.begin_dialogs:
                lines.append(f"\n预设对话：")
                for i, dialog in enumerate(target_persona.begin_dialogs[:3], 1):
                    lines.append(f"{i}. {dialog[:100]}...")
            if target_persona.tools is not None:
                if target_persona.tools:
                    lines.append(f"\n启用的工具：{', '.join(target_persona.tools)}")
                else:
                    lines.append("\n此人格已禁用所有工具")

            msg = "\n".join(lines)
            yield event.plain_result(msg)
            return

        persona_name = " ".join(l[1:])
        personas = self.context.persona_manager.personas

        target_persona = None
        for p in personas:
            if p.persona_id == persona_name:
                target_persona = p
                break

        if not target_persona:
            yield event.plain_result(
                f"未找到人格：{persona_name}\n\n输入 `/re-persona list` 查看所有可用人格。"
            )
            return

        session = event.session
        if session:
            session_id = session.session_id
            conversation_manager = self.context.conversation_manager
            db = self.context.db

            curr_cid = await conversation_manager.get_curr_conversation_id(
                umo, session_id
            )

            if curr_cid:
                conv = await conversation_manager.get_conversation(
                    umo, session_id, curr_cid
                )
                if conv:
                    conv.persona_id = target_persona.persona_id
                    await db.update_conversation(conv)
            else:
                await conversation_manager.new_conversation(
                    umo,
                    session_id,
                    persona_id=target_persona.persona_id,
                )

            system_prompt = target_persona.system_prompt or ""
            yield event.plain_result(
                f"✅ 已切换到人格：{target_persona.persona_id}\n"
                f"系统提示词：{system_prompt[:100]}..."
            )
        else:
            system_prompt = target_persona.system_prompt or ""
            yield event.plain_result(
                f"✅ 已选择人格：{target_persona.persona_id}\n"
                f"系统提示词：{system_prompt[:100]}..."
            )
