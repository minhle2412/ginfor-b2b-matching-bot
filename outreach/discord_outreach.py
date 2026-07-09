# -*- coding: utf-8 -*-
"""
Discord Outreach Integration — Giao diện duyệt Outreach trên Discord.
=======================================================================
Hiển thị preview tin nhắn outreach trên Discord với nút Approve/Reject
để admin duyệt trước khi gửi thực tế.
"""

import discord
from discord import ui
import logging
from .models import OutreachAction, OutreachChannel
from .senders import get_sender, SendResult

logger = logging.getLogger(__name__)

# Nhãn hiển thị cho từng kênh
CHANNEL_LABELS = {
    OutreachChannel.SMS: "📱 SMS",
    OutreachChannel.GMAIL: "📧 Gmail",
    OutreachChannel.FACEBOOK_COMMENT: "💬 Facebook Comment",
}


class OutreachReviewView(ui.View):
    """
    Discord View với nút Duyệt/Từ chối cho outreach review.

    Khi admin nhấn Duyệt:
    - Gửi tin nhắn qua kênh ưu tiên (stub trong prototype)
    - Đồng thời gửi Facebook comment nếu kênh ưu tiên không phải FB

    Khi admin nhấn Từ chối:
    - Cập nhật trạng thái → rejected
    - Disable các nút
    """

    def __init__(self, action: OutreachAction, engine):
        super().__init__(timeout=None)  # Không timeout — chờ admin duyệt
        self.action = action
        self.engine = engine

    @ui.button(
        label="✅ Duyệt & Gửi",
        style=discord.ButtonStyle.success,
        custom_id="outreach_approve",
    )
    async def approve_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Xử lý khi admin nhấn nút Duyệt."""
        await interaction.response.defer()

        # Đánh dấu đã duyệt
        if self.engine:
            self.engine.mark_approved(self.action.post_id)
        self.action.status = "approved"

        # Gửi qua kênh ưu tiên
        sender = get_sender(self.action.channel)
        result: SendResult = await sender.send(self.action)

        # Gửi thêm FB comment nếu kênh ưu tiên không phải FB
        fb_result = None
        if (
            self.action.channel != OutreachChannel.FACEBOOK_COMMENT
            and self.action.fb_comment_content
        ):
            fb_sender = get_sender(OutreachChannel.FACEBOOK_COMMENT)
            fb_result = await fb_sender.send(self.action)

        # Cập nhật embed trên Discord
        status_text = "✅ ĐÃ DUYỆT & GỬI"
        channel_label = CHANNEL_LABELS.get(self.action.channel, self.action.channel.value)

        if result.success:
            status_text += f"\n{channel_label}: {result.message}"
        else:
            status_text += f"\n❌ Lỗi {channel_label}: {result.error}"

        if fb_result and fb_result.success:
            status_text += f"\n💬 FB Comment: {fb_result.message}"

        embed = (
            interaction.message.embeds[0]
            if interaction.message.embeds
            else discord.Embed()
        )
        embed.color = discord.Color.green()
        embed.set_footer(
            text=f"Duyệt bởi {interaction.user.display_name} • Ginfor Outreach"
        )
        embed.add_field(name="📋 Trạng thái", value=status_text, inline=False)

        # Disable tất cả nút
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        logger.info(
            f"✅ Admin {interaction.user.display_name} đã duyệt outreach "
            f"post [{self.action.post_id}]"
        )

    @ui.button(
        label="❌ Từ chối",
        style=discord.ButtonStyle.danger,
        custom_id="outreach_reject",
    )
    async def reject_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Xử lý khi admin nhấn nút Từ chối."""
        await interaction.response.defer()

        # Đánh dấu đã từ chối
        if self.engine:
            self.engine.mark_rejected(self.action.post_id)
        self.action.status = "rejected"

        # Cập nhật embed
        embed = (
            interaction.message.embeds[0]
            if interaction.message.embeds
            else discord.Embed()
        )
        embed.color = discord.Color.red()
        embed.set_footer(
            text=f"Từ chối bởi {interaction.user.display_name} • Ginfor Outreach"
        )
        embed.add_field(
            name="📋 Trạng thái", value="❌ ĐÃ TỪ CHỐI", inline=False
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        logger.info(
            f"❌ Admin {interaction.user.display_name} đã từ chối outreach "
            f"post [{self.action.post_id}]"
        )


async def send_outreach_preview(
    bot,
    action: OutreachAction,
    engine,
    channel_id: int = None,
) -> discord.Message:
    """
    Gửi preview outreach action lên Discord để admin review.

    Hiển thị:
    - 📝 Bài viết gốc (trích đoạn)
    - 🎯 Tóm tắt nhu cầu nhận diện
    - 📡 Kênh gửi đề xuất + recipient
    - 🏢 Danh sách DN phù hợp (tóm tắt)
    - 💬 Nội dung tin nhắn đã soạn (full preview)
    - ✅ Nút Duyệt & Gửi / ❌ Nút Từ chối

    Args:
        bot: Discord bot instance
        action: OutreachAction đã soạn thảo
        engine: OutreachEngine instance (để truyền cho View)
        channel_id: ID kênh Discord để gửi preview

    Returns:
        discord.Message đã gửi, hoặc None nếu lỗi
    """
    # Tìm channel phù hợp
    channel = None
    if channel_id:
        channel = bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                pass

    if not channel:
        logger.error("❌ Không tìm thấy channel để gửi outreach preview")
        return None

    # Xây dựng embed preview
    channel_label = CHANNEL_LABELS.get(action.channel, action.channel.value)

    embed = discord.Embed(
        title=f"📨 [Outreach Review] — {channel_label}",
        description=(
            "Bài viết buyer được phát hiện. "
            "Vui lòng duyệt nội dung trước khi gửi đi."
        ),
        color=discord.Color(0xFF9900),  # Cam = đang chờ duyệt
        timestamp=action.created_at,
    )

    # Bài viết gốc (trích đoạn)
    post_preview = action.post_text[:400]
    if len(action.post_text) > 400:
        post_preview += "..."
    embed.add_field(
        name="📝 Bài viết gốc",
        value=f"```\n{post_preview}\n```",
        inline=False,
    )

    # Nhu cầu nhận diện
    embed.add_field(
        name="🎯 Nhu cầu nhận diện",
        value=f"**{action.buyer_need_summary}**",
        inline=True,
    )

    # Kênh gửi + người nhận
    embed.add_field(
        name="📡 Kênh gửi",
        value=f"{channel_label}\n👤 `{action.recipient}`",
        inline=True,
    )

    # Danh sách DN phù hợp (tóm tắt)
    companies_text = ""
    for i, m in enumerate(action.matches_used[:5]):
        comp = m["company"]
        score_pct = int(m["total_score"] * 100)
        companies_text += (
            f"{i+1}. **{comp['name']}** ({score_pct}%) — "
            f"{comp.get('city', 'N/A')}\n"
        )

    embed.add_field(
        name=f"🏢 Top {len(action.matches_used)} DN phù hợp",
        value=companies_text or "*(Không có)*",
        inline=False,
    )

    # Nội dung tin nhắn chính (preview)
    msg_preview = action.message_content[:800]
    if len(action.message_content) > 800:
        msg_preview += "\n..."
    embed.add_field(
        name=f"💬 Nội dung {channel_label}",
        value=f"```\n{msg_preview}\n```",
        inline=False,
    )

    # Nếu kênh ưu tiên không phải FB → hiển thị thêm FB comment preview
    if (
        action.channel != OutreachChannel.FACEBOOK_COMMENT
        and action.fb_comment_content
    ):
        fb_preview = action.fb_comment_content[:500]
        if len(action.fb_comment_content) > 500:
            fb_preview += "\n..."
        embed.add_field(
            name="💬 Facebook Comment (mặc định)",
            value=f"```\n{fb_preview}\n```",
            inline=False,
        )

    # Link bài viết
    if action.post_url:
        embed.add_field(
            name="🔗 Link bài viết",
            value=f"[Xem trên Facebook]({action.post_url})",
            inline=True,
        )

    embed.set_footer(
        text=f"Post ID: {action.post_id} • Ginfor Outreach • Đang chờ duyệt"
    )

    # Tạo View với nút Approve/Reject
    view = OutreachReviewView(action, engine)

    try:
        msg = await channel.send(embed=embed, view=view)
        logger.info(
            f"📨 Đã gửi outreach preview cho post [{action.post_id}] lên Discord"
        )
        return msg
    except Exception as e:
        logger.error(f"❌ Lỗi gửi outreach preview: {e}")
        return None
