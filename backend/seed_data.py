"""Seed script to populate forum database with initial data"""
import asyncio
from datetime import datetime, timedelta
import json
from app.database import async_session, engine, Base
from app.models import (
    User, UserRole, ForumSection, ForumBoard, Thread, Post,
    Badge, AppSettings, Giveaway, DailyRewardConfig
)


async def seed_database():
    """Populate database with forum data"""
    
    async with async_session() as db:
        print("🌱 Starting forum database seeding...")
        
        # ─── AppSettings ─────────────────────────────────────────────────────
        from sqlalchemy import select
        settings_check = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        if not settings_check.scalar_one_or_none():
            db.add(AppSettings(
                id=1,
                app_name="Forum",
                bot_username="ForumBot",
                withdrawal_fee_percent=2.0
            ))
            print("✅ Created AppSettings")
        
        # ─── Users ───────────────────────────────────────────────────────────
        users_data = [
            {
                "telegram_id": "admin_1001",
                "username": "admin",
                "first_name": "Admin",
                "role": UserRole.ADMIN,
                "balance": 1000.0,
                "rep_positive": 50,
            },
            {
                "telegram_id": "mod_1001",
                "username": "moderator",
                "first_name": "Mod",
                "role": UserRole.MODERATOR,
                "balance": 100.0,
                "rep_positive": 25,
            },
            {
                "telegram_id": "user_1001",
                "username": "johndoe",
                "first_name": "John",
                "role": UserRole.USER,
                "balance": 50.0,
                "rep_positive": 10,
            },
            {
                "telegram_id": "user_1002",
                "username": "jane_smith",
                "first_name": "Jane",
                "role": UserRole.USER,
                "balance": 25.0,
                "rep_positive": 5,
            },
            {
                "telegram_id": "trial_1001",
                "username": "newbie",
                "first_name": "New",
                "role": UserRole.TRIAL,
                "balance": 0.0,
                "rep_positive": 0,
            },
        ]
        
        users = []
        for user_data in users_data:
            check = await db.execute(select(User).where(User.telegram_id == user_data["telegram_id"]))
            if not check.scalar_one_or_none():
                # Seeded users are pre-registered (username already set), so skip the
                # onboarding/registration modal — it only shows when is_setup_complete
                # is false. Lets the seeded app land straight on real content.
                user = User(**user_data, is_setup_complete=True)
                db.add(user)
                users.append(user)
        
        await db.flush()
        print(f"✅ Created {len(users)} users")
        
        # Get all users for reference
        result = await db.execute(select(User))
        all_users = {u.telegram_id: u for u in result.scalars().all()}
        admin_user = all_users.get("admin_1001")
        john_user = all_users.get("user_1001")
        jane_user = all_users.get("user_1002")
        
        # ─── Forum Sections ──────────────────────────────────────────────────
        sections_data = [
            {"name": "General", "slug": "general", "description": "General discussion and community chat", "sort_order": 1},
            {"name": "Trading", "slug": "trading", "description": "Buy, sell, and trade with other members", "sort_order": 2},
            {"name": "Support", "slug": "support", "description": "Get help and assistance", "sort_order": 3},
            {"name": "Off-Topic", "slug": "off-topic", "description": "Everything else", "sort_order": 4},
        ]
        
        sections = []
        for section_data in sections_data:
            check = await db.execute(select(ForumSection).where(ForumSection.name == section_data["name"]))
            if not check.scalar_one_or_none():
                section = ForumSection(**section_data)
                db.add(section)
                sections.append(section)
        
        await db.flush()
        print(f"✅ Created {len(sections)} forum sections")
        
        # Get sections for reference
        result = await db.execute(select(ForumSection))
        all_sections = {s.name: s for s in result.scalars().all()}
        
        # ─── Forum Boards ────────────────────────────────────────────────────
        boards_data = [
            # General section
            {"name": "Announcements", "slug": "announcements", "description": "Official announcements and updates", "section_id": all_sections["General"].id, "sort_order": 1},
            {"name": "Introductions", "slug": "introductions", "description": "Introduce yourself to the community", "section_id": all_sections["General"].id, "sort_order": 2},
            {"name": "Feedback", "slug": "feedback", "description": "Share your feedback and suggestions", "section_id": all_sections["General"].id, "sort_order": 3},
            # Trading section
            {"name": "Marketplace", "slug": "marketplace", "description": "Buy and sell items", "section_id": all_sections["Trading"].id, "sort_order": 1},
            {"name": "Services", "slug": "services", "description": "Offer and request services", "section_id": all_sections["Trading"].id, "sort_order": 2},
            {"name": "Reputation", "slug": "reputation", "description": "Reputation and trade feedback threads", "section_id": all_sections["Trading"].id, "sort_order": 3},
            # Support section
            {"name": "Help & Questions", "slug": "help-questions", "description": "Ask questions and get help", "section_id": all_sections["Support"].id, "sort_order": 1},
            {"name": "Tutorials", "slug": "tutorials", "description": "Guides and tutorials", "section_id": all_sections["Support"].id, "sort_order": 2},
            # Off-Topic section
            {"name": "Lounge", "slug": "lounge", "description": "Casual chat and discussions", "section_id": all_sections["Off-Topic"].id, "sort_order": 1},
            {"name": "Media", "slug": "media", "description": "Share images, videos, and memes", "section_id": all_sections["Off-Topic"].id, "sort_order": 2},
        ]
        
        boards = []
        for board_data in boards_data:
            check = await db.execute(select(ForumBoard).where(ForumBoard.name == board_data["name"]))
            if not check.scalar_one_or_none():
                board = ForumBoard(**board_data)
                db.add(board)
                boards.append(board)
        
        await db.flush()
        print(f"✅ Created {len(boards)} forum boards")
        
        # Get boards for reference
        result = await db.execute(select(ForumBoard))
        all_boards = {b.name: b for b in result.scalars().all()}
        
        # ─── Badges ──────────────────────────────────────────────────────────
        badges_data = [
            {"name": "OG", "description": "Original member", "color": "#FFD700", "icon": "crown", "icon_style": "glow", "price": 0.0, "is_purchasable": False},
            {"name": "VIP", "description": "VIP member", "color": "#8B5CF6", "icon": "gem", "icon_style": "glow", "price": 25.0, "is_purchasable": False},
            {"name": "Premium", "description": "Premium supporter", "color": "#06B6D4", "icon": "sparkles", "icon_style": "sparkle", "price": 80.0, "is_purchasable": False},
            {"name": "Bronze Bar", "description": "Supporter — stackable support badge", "color": "#CD7F32", "icon": "medal", "icon_style": "default", "price": 10.0, "is_purchasable": False,
             "multi_purchase": True, "reward_xp": 50},
            {"name": "Silver Bar", "description": "Supporter — stackable support badge", "color": "#C0C0C0", "icon": "medal", "icon_style": "ring", "price": 25.0, "is_purchasable": False,
             "multi_purchase": True, "reward_xp": 100},
            {"name": "Gold Bar", "description": "One-time support — unlocks full membership access", "color": "#FFD700", "icon": "star", "icon_style": "glow", "price": 50.0, "is_purchasable": False,
             "multi_purchase": True, "reward_xp": 200, "reward_role": "USER"},
            {"name": "Verified", "description": "Verified trader", "color": "#10B981", "icon": "shield-check", "icon_style": "ring", "price": 0.0, "is_purchasable": False},
            {"name": "Helper", "description": "Community helper", "color": "#F59E0B", "icon": "heart-handshake", "icon_style": "pulse", "price": 10.0, "is_purchasable": False},
            {"name": "Contributor", "description": "Active contributor", "color": "#EC4899", "icon": "git-pull-request", "icon_style": "ring", "price": 15.0, "is_purchasable": False},
            {"name": "Early Bird", "description": "Early adopter", "color": "#EF4444", "icon": "bird", "icon_style": "default", "price": 5.0, "is_purchasable": False},
            # Achievement badges (auto-awarded)
            {"name": "First Words", "description": "Posted your first reply", "color": "#A78BFA", "icon": "message-circle", "icon_style": "default", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"post_count": 1}), "reward_xp": 10},
            {"name": "Chatterbox", "description": "Posted 50 replies", "color": "#818CF8", "icon": "messages-square", "icon_style": "ring", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"post_count": 50}), "reward_xp": 100},
            {"name": "Century Poster", "description": "Posted 100 replies", "color": "#6366F1", "icon": "message-square-quote", "icon_style": "glow", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"post_count": 100}), "reward_xp": 250, "reward_balance": 1.0},
            {"name": "Prolific Poster", "description": "Posted 500 replies", "color": "#4F46E5", "icon": "message-square-quote", "icon_style": "sparkle", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"post_count": 500}), "reward_xp": 1000, "reward_balance": 5.0},
            {"name": "Thread Starter", "description": "Created your first thread", "color": "#34D399", "icon": "pen-square", "icon_style": "default", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"thread_count": 1}), "reward_xp": 15},
            {"name": "Conversation Maker", "description": "Created 10 threads", "color": "#10B981", "icon": "layout-list", "icon_style": "ring", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"thread_count": 10}), "reward_xp": 150, "reward_balance": 1.0},
            {"name": "Liked", "description": "Received 10 likes", "color": "#F472B6", "icon": "heart", "icon_style": "default", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"like_count": 10}), "reward_xp": 50},
            {"name": "Popular", "description": "Received 50 likes", "color": "#EC4899", "icon": "flame", "icon_style": "glow", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"like_count": 50}), "reward_xp": 200, "reward_balance": 2.0},
            {"name": "Reputable", "description": "Earned 25 positive reputation", "color": "#FBBF24", "icon": "thumbs-up", "icon_style": "ring", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"rep_positive": 25}), "reward_xp": 100},
            {"name": "Trusted", "description": "Earned 50 positive reputation", "color": "#F59E0B", "icon": "shield", "icon_style": "glow", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"rep_positive": 50}), "reward_xp": 250, "reward_balance": 2.0},
            {"name": "Legendary Rep", "description": "Earned 100 positive reputation", "color": "#EF4444", "icon": "trophy", "icon_style": "sparkle", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"rep_positive": 100}), "reward_xp": 500, "reward_balance": 5.0},
            {"name": "7 Day Streak", "description": "Logged in 7 days in a row", "color": "#06B6D4", "icon": "zap", "icon_style": "pulse", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"login_streak": 7}), "reward_xp": 70, "reward_balance": 0.50},
            {"name": "30 Day Streak", "description": "Logged in 30 days in a row", "color": "#0EA5E9", "icon": "flame", "icon_style": "glow", "price": 0.0, "is_purchasable": False,
             "auto_award_criteria": json.dumps({"login_streak": 30}), "reward_xp": 300, "reward_balance": 3.0},
        ]
        
        badges = []
        for badge_data in badges_data:
            check = await db.execute(select(Badge).where(Badge.name == badge_data["name"]))
            existing = check.scalar_one_or_none()
            if existing:
                updated = False
                if existing.icon is None and badge_data.get("icon"):
                    existing.icon = badge_data["icon"]
                    updated = True
                if (existing.icon_style is None or existing.icon_style == "default") and badge_data.get("icon_style") and badge_data["icon_style"] != "default":
                    existing.icon_style = badge_data["icon_style"]
                    updated = True
                if updated:
                    badges.append(existing)
            else:
                auto_criteria = badge_data.pop("auto_award_criteria", None)
                reward_xp = badge_data.pop("reward_xp", 0)
                reward_balance = badge_data.pop("reward_balance", 0.0)
                reward_role = badge_data.pop("reward_role", None)
                multi_purchase = badge_data.pop("multi_purchase", False)
                badge = Badge(**badge_data)
                if auto_criteria:
                    badge.auto_award_criteria = auto_criteria
                badge.reward_xp = reward_xp
                badge.reward_balance = reward_balance
                if reward_role:
                    badge.reward_role = reward_role
                badge.multi_purchase = multi_purchase
                db.add(badge)
                badges.append(badge)
                badge_data["auto_award_criteria"] = auto_criteria
                badge_data["reward_xp"] = reward_xp
                badge_data["reward_balance"] = reward_balance
                if reward_role:
                    badge_data["reward_role"] = reward_role
        
        await db.flush()
        print(f"✅ Created {len(badges)} badges")

        # ─── Daily Reward Config ─────────────────────────────────────────────
        daily_reward_tiers = [
            {"day": 1, "xp_amount": 10, "balance_amount": 0.10},
            {"day": 2, "xp_amount": 10, "balance_amount": 0.10},
            {"day": 3, "xp_amount": 10, "balance_amount": 0.10},
            {"day": 4, "xp_amount": 10, "balance_amount": 0.10},
            {"day": 5, "xp_amount": 15, "balance_amount": 0.15},
            {"day": 6, "xp_amount": 15, "balance_amount": 0.15},
            {"day": 7, "xp_amount": 20, "balance_amount": 0.20},
            {"day": 14, "xp_amount": 25, "balance_amount": 0.25},
            {"day": 21, "xp_amount": 30, "balance_amount": 0.30},
            {"day": 30, "xp_amount": 50, "balance_amount": 0.50},
            {"day": 50, "xp_amount": 60, "balance_amount": 0.60},
            {"day": 75, "xp_amount": 80, "balance_amount": 0.80},
            {"day": 100, "xp_amount": 100, "balance_amount": 1.00},
        ]

        streak_7_badge = await db.scalar(select(Badge).where(Badge.name == "7 Day Streak"))
        streak_30_badge = await db.scalar(select(Badge).where(Badge.name == "30 Day Streak"))

        rewards_created = 0
        for tier in daily_reward_tiers:
            existing = await db.execute(
                select(DailyRewardConfig).where(DailyRewardConfig.day == tier["day"])
            )
            if not existing.scalar_one_or_none():
                config = DailyRewardConfig(
                    day=tier["day"],
                    xp_amount=tier["xp_amount"],
                    balance_amount=tier["balance_amount"],
                )
                if tier["day"] == 7 and streak_7_badge:
                    config.badge_id = streak_7_badge.id
                elif tier["day"] == 30 and streak_30_badge:
                    config.badge_id = streak_30_badge.id
                db.add(config)
                rewards_created += 1

        print(f"✅ Created {rewards_created} daily reward configs")
        
        # ─── Sample Threads ──────────────────────────────────────────────────
        if admin_user and john_user:
            threads_data = [
                {
                    "title": "Welcome to the Forum!",
                    "content": "Welcome everyone to our new forum platform! Please read the rules and enjoy your stay.\n\nFeel free to introduce yourself in the Introductions board.",
                    "board_id": all_boards["Announcements"].id,
                    "author_id": admin_user.id,
                    "is_pinned": True,
                },
                {
                    "title": "Forum Rules - Read Before Posting",
                    "content": "1. Be respectful to all members\n2. No spam or self-promotion\n3. No illegal content\n4. Use appropriate boards\n5. Follow trading guidelines\n\nViolations may result in warnings or bans.",
                    "board_id": all_boards["Announcements"].id,
                    "author_id": admin_user.id,
                    "is_pinned": True,
                },
                {
                    "title": "Hi everyone, I'm John!",
                    "content": "Hey all! Just joined this community. Looking forward to meeting everyone and participating in discussions.",
                    "board_id": all_boards["Introductions"].id,
                    "author_id": john_user.id,
                },
            ]
            
            threads = []
            for thread_data in threads_data:
                check = await db.execute(select(Thread).where(Thread.title == thread_data["title"]))
                if not check.scalar_one_or_none():
                    thread = Thread(**thread_data)
                    db.add(thread)
                    threads.append(thread)
            
            await db.flush()
            print(f"✅ Created {len(threads)} sample threads")
            
            # ─── Sample Posts (Replies) ──────────────────────────────────────
            if jane_user and threads:
                result = await db.execute(select(Thread).where(Thread.title == "Hi everyone, I'm John!"))
                intro_thread = result.scalar_one_or_none()
                
                if intro_thread:
                    posts_data = [
                        {
                            "content": "Welcome to the forum, John! Hope you enjoy it here.",
                            "thread_id": intro_thread.id,
                            "author_id": jane_user.id,
                        },
                        {
                            "content": "Thanks Jane! Already liking the community vibes.",
                            "thread_id": intro_thread.id,
                            "author_id": john_user.id,
                        },
                    ]
                    
                    for post_data in posts_data:
                        post = Post(**post_data)
                        db.add(post)
                    
                    intro_thread.reply_count = len(posts_data)
                    print(f"✅ Created {len(posts_data)} sample posts")
        
        # ─── Sample Giveaway ─────────────────────────────────────────────────
        check = await db.execute(select(Giveaway).where(Giveaway.title == "Welcome Giveaway"))
        if not check.scalar_one_or_none():
            giveaway = Giveaway(
                title="Welcome Giveaway",
                description="Celebrating our forum launch! One lucky winner gets $25 balance.",
                prize="$25 Balance",
                ends_at=datetime.utcnow() + timedelta(days=7),
            )
            db.add(giveaway)
            print("✅ Created sample giveaway")
        
        await db.commit()
        print("🎉 Database seeding complete!")


async def main():
    """Main entry point"""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed data
    await seed_database()


if __name__ == "__main__":
    asyncio.run(main())
