// 共享弹窗与工具组件（DailyReward、Onboarding、TrialWelcome、SessionExpiry、
// Confirm、Report、UserList、ErrorBoundary、MarkdownToolbar、BannerRows）。
export default {
  // Shared
  'modals.maybe_later': '以后再说',

  // DailyRewardModal
  'modals.daily.title': '每日奖励',
  'modals.daily.streak_line': '已连续签到 {n} 天！继续保持！',
  'modals.daily.come_back': '每天回来签到，奖励更丰厚！',
  'modals.daily.xp_bonus': 'XP 奖励',
  'modals.daily.balance_bonus': '余额奖励',
  'modals.daily.badge': '徽章',
  'modals.daily.streak': '连续签到',
  'modals.daily.day_n': '第 {n} 天',
  'modals.daily.claiming': '领取中...',
  'modals.daily.claim': '领取奖励',

  // OnboardingModal
  'modals.onboarding.pw_min': '密码至少需要 6 个字符',
  'modals.onboarding.pw_digit': '密码至少需要包含 1 个数字',
  'modals.onboarding.name_required': '请填写显示名称',
  'modals.onboarding.pw_mismatch': '两次输入的密码不一致',
  'modals.onboarding.setup_failed': '设置失败',
  'modals.onboarding.title': '欢迎来到论坛',
  'modals.onboarding.subtitle': '设置用户名和密码以保护你的账户',
  'modals.onboarding.display_name': '显示名称',
  'modals.onboarding.display_name_ph': '你的名字',
  'modals.onboarding.display_name_hint': '将显示在你的个人资料、主题和帖子中。以后修改需支付 $20。',
  'modals.onboarding.password': '密码',
  'modals.onboarding.password_ph': '6 个以上字符，至少 1 个数字',
  'modals.onboarding.password_hint': '须为 6 个以上字符，且至少包含 1 个数字',
  'modals.onboarding.confirm_password': '确认密码',
  'modals.onboarding.confirm_password_ph': '再次输入密码',
  'modals.onboarding.show_handle': '显示我的 Telegram 用户名',
  'modals.onboarding.handle_desc_before': '你的 ',
  'modals.onboarding.handle_desc_after': ' 将显示在你的个人资料、主题和帖子中。关闭后将只显示你的显示名称。你可以随时在设置中更改。',
  'modals.onboarding.creating': '正在创建账户...',
  'modals.onboarding.enter': '进入论坛',
  'modals.onboarding.ready_title': '账户已就绪',
  'modals.onboarding.ready_subtitle': '账户设置完成。现在来完善你的个人资料吧。',
  'modals.onboarding.set_avatar': '设置头像',
  'modals.onboarding.set_avatar_desc': '上传头像，让大家认识你',
  'modals.onboarding.write_bio': '填写个人简介',
  'modals.onboarding.write_bio_desc': '向社区介绍一下自己',
  'modals.onboarding.settings': '配置设置',
  'modals.onboarding.settings_desc': '通知偏好与账户选项',
  'modals.onboarding.skip': '暂时跳过',

  // TrialWelcomeModal
  'modals.trial.title': '欢迎来到论坛！',
  'modals.trial.intro_before': '你目前处于',
  'modals.trial.intro_mode': '试用模式',
  'modals.trial.intro_after': '，访问权限有限。',
  'modals.trial.step1_title': '自我介绍',
  'modals.trial.step1_before': '在',
  'modals.trial.step1_board': '申请完整权限',
  'modals.trial.step1_after': '板块发帖——告诉社区你是谁、为什么来到这里。',
  'modals.trial.step2_title': '赢得声望',
  'modals.trial.step2_desc': '现有成员会阅读你的介绍，如果认为你值得获得权限，就会给你 +rep。',
  'modals.trial.step3_title': '获得完整权限',
  'modals.trial.step3_before': '获得',
  'modals.trial.step3_strong': '资深成员的 +rep',
  'modals.trial.step3_after': '后，管理员会将你升级为正式成员！',
  'modals.trial.request_access': '申请完整权限',
  'modals.trial.purchase_premium': '购买 Premium',

  // SessionExpiryModal
  'modals.session.title': '会话即将过期',
  'modals.session.expires_in': '将于 {time} 后过期',
  'modals.session.body': '由于长时间未操作，你的登录会话即将过期。要保持登录吗？',
  'modals.session.logout': '退出登录',
  'modals.session.stay': '保持登录',

  // ConfirmModal
  'modals.confirm.title': '确认操作',

  // ReportModal
  'modals.report.intro': '向版主举报{target}。',
  'modals.report.target_post': '这个帖子',
  'modals.report.target_thread': '这个主题',
  'modals.report.target_user': '这位用户',
  'modals.report.reason': '原因',
  'modals.report.reason_spam': '垃圾信息',
  'modals.report.reason_scam': '诈骗或欺诈',
  'modals.report.reason_abuse': '辱骂行为',
  'modals.report.reason_illegal': '违法内容',
  'modals.report.reason_other': '其他',
  'modals.report.details': '详细说明（可选）',
  'modals.report.details_ph': '任何有助于版主了解问题的信息...',
  'modals.report.submitted': '举报已提交——版主会尽快处理',
  'modals.report.failed': '举报提交失败',
  'modals.report.submitting': '提交中…',
  'modals.report.submit': '提交举报',

  // UserListModal
  'modals.userlist.empty': '这里还没有人',

  // ErrorBoundary
  'modals.error.title': '出错了',
  'modals.error.body': '发生了意外错误。请尝试返回首页。',
  'modals.error.go_home': '返回首页',

  // MarkdownToolbar
  'modals.md.bold': '粗体',
  'modals.md.italic': '斜体',
  'modals.md.strikethrough': '删除线',
  'modals.md.h1': '标题 1',
  'modals.md.h2': '标题 2',
  'modals.md.inline_code': '行内代码',
  'modals.md.code_block': '代码块',
  'modals.md.insert_link': '插入链接',
  'modals.md.quote': '引用',
  'modals.md.list': '列表',
  'modals.md.upload_image': '上传图片',
  'modals.md.invalid_url': '请输入有效的 URL',
  'modals.md.upload_failed': '图片上传失败',
  'modals.md.link_text_ph': '链接文字（可选）',
  'modals.md.insert': '插入',

  // BannerRows
  'modals.banner.learn_more': '了解更多',
}
