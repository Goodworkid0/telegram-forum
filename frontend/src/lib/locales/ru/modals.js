// Общие модальные окна и вспомогательные компоненты (DailyReward, Onboarding,
// TrialWelcome, SessionExpiry, Confirm, Report, UserList, ErrorBoundary,
// MarkdownToolbar, BannerRows).
export default {
  // Shared
  'modals.maybe_later': 'Может быть, позже',

  // DailyRewardModal
  'modals.daily.title': 'Ежедневная награда',
  'modals.daily.streak_line': 'Серия входов: {n} дн. подряд! Так держать!',
  'modals.daily.come_back': 'Заходите каждый день, чтобы получать больше наград!',
  'modals.daily.xp_bonus': 'Бонус XP',
  'modals.daily.balance_bonus': 'Бонус к балансу',
  'modals.daily.badge': 'Значок',
  'modals.daily.streak': 'Серия',
  'modals.daily.day_n': 'День {n}',
  'modals.daily.claiming': 'Получение...',
  'modals.daily.claim': 'Забрать награду',

  // OnboardingModal
  'modals.onboarding.pw_min': 'Пароль должен содержать не менее 6 символов',
  'modals.onboarding.pw_digit': 'Пароль должен содержать хотя бы 1 цифру',
  'modals.onboarding.name_required': 'Укажите отображаемое имя',
  'modals.onboarding.pw_mismatch': 'Пароли не совпадают',
  'modals.onboarding.setup_failed': 'Не удалось завершить настройку',
  'modals.onboarding.title': 'Добро пожаловать на форум',
  'modals.onboarding.subtitle': 'Выберите имя пользователя и пароль, чтобы защитить аккаунт',
  'modals.onboarding.display_name': 'Отображаемое имя',
  'modals.onboarding.display_name_ph': 'Ваше имя',
  'modals.onboarding.display_name_hint': 'Отображается в вашем профиле, темах и сообщениях. Смена имени позже стоит $20.',
  'modals.onboarding.password': 'Пароль',
  'modals.onboarding.password_ph': '6+ символов, минимум 1 цифра',
  'modals.onboarding.password_hint': 'Не менее 6 символов и хотя бы 1 цифра',
  'modals.onboarding.confirm_password': 'Подтвердите пароль',
  'modals.onboarding.confirm_password_ph': 'введите пароль ещё раз',
  'modals.onboarding.show_handle': 'Показывать мой Telegram-ник',
  'modals.onboarding.handle_desc_before': 'Ваш ',
  'modals.onboarding.handle_desc_after': ' будет виден в вашем профиле, темах и сообщениях. Отключите, чтобы показывать только отображаемое имя. Это можно изменить в любой момент в настройках.',
  'modals.onboarding.creating': 'Создание аккаунта...',
  'modals.onboarding.enter': 'Войти на форум',
  'modals.onboarding.ready_title': 'Аккаунт готов',
  'modals.onboarding.ready_subtitle': 'Аккаунт настроен. Теперь настройте свой профиль.',
  'modals.onboarding.set_avatar': 'Установить фото профиля',
  'modals.onboarding.set_avatar_desc': 'Загрузите аватар, чтобы вас узнавали',
  'modals.onboarding.write_bio': 'Заполните био',
  'modals.onboarding.write_bio_desc': 'Расскажите сообществу о себе',
  'modals.onboarding.settings': 'Настройте параметры',
  'modals.onboarding.settings_desc': 'Уведомления и параметры аккаунта',
  'modals.onboarding.skip': 'Пропустить',

  // TrialWelcomeModal
  'modals.trial.title': 'Добро пожаловать на форум!',
  'modals.trial.intro_before': 'Сейчас у вас ',
  'modals.trial.intro_mode': 'пробный режим',
  'modals.trial.intro_after': ' с ограниченным доступом.',
  'modals.trial.step1_title': 'Представьтесь',
  'modals.trial.step1_before': 'Напишите в разделе ',
  'modals.trial.step1_board': 'Запрос полного доступа',
  'modals.trial.step1_after': ' — расскажите сообществу, кто вы и зачем пришли.',
  'modals.trial.step2_title': 'Заработайте репутацию',
  'modals.trial.step2_desc': 'Участники форума прочитают ваше представление и поставят вам +rep, если сочтут, что вам стоит дать доступ.',
  'modals.trial.step3_title': 'Получите полный доступ',
  'modals.trial.step3_before': 'Наберите ',
  'modals.trial.step3_strong': '+rep от опытных участников',
  'modals.trial.step3_after': ' — и администратор повысит вас до полноправного участника!',
  'modals.trial.request_access': 'Запросить полный доступ',
  'modals.trial.purchase_premium': 'Купить Premium',

  // SessionExpiryModal
  'modals.session.title': 'Сессия истекает',
  'modals.session.expires_in': 'Истекает через {time}',
  'modals.session.body': 'Ваша сессия скоро завершится из-за неактивности. Хотите остаться в системе?',
  'modals.session.logout': 'Выйти',
  'modals.session.stay': 'Остаться в системе',

  // ConfirmModal
  'modals.confirm.title': 'Подтвердите действие',

  // ReportModal
  'modals.report.intro': 'Отправить модераторам жалобу на {target}.',
  'modals.report.target_post': 'этот пост',
  'modals.report.target_thread': 'эту тему',
  'modals.report.target_user': 'этого пользователя',
  'modals.report.reason': 'Причина',
  'modals.report.reason_spam': 'Спам',
  'modals.report.reason_scam': 'Мошенничество',
  'modals.report.reason_abuse': 'Оскорбительное поведение',
  'modals.report.reason_illegal': 'Незаконный контент',
  'modals.report.reason_other': 'Другое',
  'modals.report.details': 'Подробности (необязательно)',
  'modals.report.details_ph': 'Всё, что поможет модераторам разобраться в ситуации...',
  'modals.report.submitted': 'Жалоба отправлена — модератор её рассмотрит',
  'modals.report.failed': 'Не удалось отправить жалобу',
  'modals.report.submitting': 'Отправка…',
  'modals.report.submit': 'Отправить жалобу',

  // UserListModal
  'modals.userlist.empty': 'Здесь пока никого нет',

  // ErrorBoundary
  'modals.error.title': 'Что-то пошло не так',
  'modals.error.body': 'Произошла непредвиденная ошибка. Попробуйте вернуться на главную страницу.',
  'modals.error.go_home': 'На главную',

  // MarkdownToolbar
  'modals.md.bold': 'Жирный',
  'modals.md.italic': 'Курсив',
  'modals.md.strikethrough': 'Зачёркнутый',
  'modals.md.h1': 'Заголовок 1',
  'modals.md.h2': 'Заголовок 2',
  'modals.md.inline_code': 'Встроенный код',
  'modals.md.code_block': 'Блок кода',
  'modals.md.insert_link': 'Вставить ссылку',
  'modals.md.quote': 'Цитата',
  'modals.md.list': 'Список',
  'modals.md.upload_image': 'Загрузить изображение',
  'modals.md.invalid_url': 'Введите корректный URL',
  'modals.md.upload_failed': 'Не удалось загрузить изображение',
  'modals.md.link_text_ph': 'Текст ссылки (необязательно)',
  'modals.md.insert': 'Вставить',

  // BannerRows
  'modals.banner.learn_more': 'Подробнее',
}
