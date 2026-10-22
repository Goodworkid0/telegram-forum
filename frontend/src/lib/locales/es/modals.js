// Ventanas modales y componentes auxiliares compartidos (DailyReward, Onboarding,
// TrialWelcome, SessionExpiry, Confirm, Report, UserList, ErrorBoundary,
// MarkdownToolbar, BannerRows).
export default {
  // Shared
  'modals.maybe_later': 'Quizás más tarde',

  // DailyRewardModal
  'modals.daily.title': 'Recompensa diaria',
  'modals.daily.streak_line': '¡Racha de {n} días! ¡Sigue así!',
  'modals.daily.come_back': '¡Vuelve cada día para recibir recompensas más grandes!',
  'modals.daily.xp_bonus': 'Bono de XP',
  'modals.daily.balance_bonus': 'Bono de saldo',
  'modals.daily.badge': 'Insignia',
  'modals.daily.streak': 'Racha',
  'modals.daily.day_n': 'Día {n}',
  'modals.daily.claiming': 'Reclamando...',
  'modals.daily.claim': 'Reclamar recompensa',

  // OnboardingModal
  'modals.onboarding.pw_min': 'La contraseña debe tener al menos 6 caracteres',
  'modals.onboarding.pw_digit': 'La contraseña debe contener al menos 1 dígito',
  'modals.onboarding.name_required': 'El nombre visible es obligatorio',
  'modals.onboarding.pw_mismatch': 'Las contraseñas no coinciden',
  'modals.onboarding.setup_failed': 'Error al completar la configuración',
  'modals.onboarding.title': 'Bienvenido al Foro',
  'modals.onboarding.subtitle': 'Elige un nombre de usuario y una contraseña para proteger tu cuenta',
  'modals.onboarding.display_name': 'Nombre visible',
  'modals.onboarding.display_name_ph': 'Tu nombre',
  'modals.onboarding.display_name_hint': 'Se muestra en tu perfil, temas y publicaciones. Cambiarlo más adelante cuesta $20.',
  'modals.onboarding.password': 'Contraseña',
  'modals.onboarding.password_ph': '6+ caracteres, 1+ dígito',
  'modals.onboarding.password_hint': 'Debe tener 6+ caracteres y al menos 1 dígito',
  'modals.onboarding.confirm_password': 'Confirmar contraseña',
  'modals.onboarding.confirm_password_ph': 'vuelve a escribir la contraseña',
  'modals.onboarding.show_handle': 'Mostrar mi usuario de Telegram',
  'modals.onboarding.handle_desc_before': 'Tu ',
  'modals.onboarding.handle_desc_after': ' será visible en tu perfil, temas y publicaciones. Desactívalo para mostrar solo tu nombre visible. Puedes cambiarlo en cualquier momento en Ajustes.',
  'modals.onboarding.creating': 'Creando cuenta...',
  'modals.onboarding.enter': 'Entrar al Foro',
  'modals.onboarding.ready_title': 'Cuenta lista',
  'modals.onboarding.ready_subtitle': 'Tu cuenta está configurada. Ahora personaliza tu perfil.',
  'modals.onboarding.set_avatar': 'Establecer foto de perfil',
  'modals.onboarding.set_avatar_desc': 'Sube un avatar para que la gente te reconozca',
  'modals.onboarding.write_bio': 'Escribe tu biografía',
  'modals.onboarding.write_bio_desc': 'Cuéntale a la comunidad sobre ti',
  'modals.onboarding.settings': 'Configurar ajustes',
  'modals.onboarding.settings_desc': 'Preferencias de notificaciones y opciones de la cuenta',
  'modals.onboarding.skip': 'Omitir por ahora',

  // TrialWelcomeModal
  'modals.trial.title': '¡Bienvenido al Foro!',
  'modals.trial.intro_before': 'Actualmente estás en ',
  'modals.trial.intro_mode': 'Modo de prueba',
  'modals.trial.intro_after': ' con acceso limitado.',
  'modals.trial.step1_title': 'Preséntate',
  'modals.trial.step1_before': 'Publica en ',
  'modals.trial.step1_board': 'Solicitar acceso completo',
  'modals.trial.step1_after': ' — cuéntale a la comunidad quién eres y por qué estás aquí.',
  'modals.trial.step2_title': 'Gana reputación',
  'modals.trial.step2_desc': 'Los miembros existentes leerán tu presentación y te darán +rep si creen que mereces el acceso.',
  'modals.trial.step3_title': 'Consigue acceso completo',
  'modals.trial.step3_before': 'Consigue ',
  'modals.trial.step3_strong': '+rep de miembros establecidos',
  'modals.trial.step3_after': ' ¡y un administrador te ascenderá a miembro completo!',
  'modals.trial.request_access': 'Solicitar acceso completo',
  'modals.trial.purchase_premium': 'Comprar Premium',

  // SessionExpiryModal
  'modals.session.title': 'Sesión a punto de expirar',
  'modals.session.expires_in': 'Expira en {time}',
  'modals.session.body': 'Tu sesión está a punto de expirar por inactividad. ¿Quieres seguir conectado?',
  'modals.session.logout': 'Cerrar sesión',
  'modals.session.stay': 'Seguir conectado',

  // ConfirmModal
  'modals.confirm.title': 'Confirmar acción',

  // ReportModal
  'modals.report.intro': 'Reportar {target} a los moderadores.',
  'modals.report.target_post': 'esta publicación',
  'modals.report.target_thread': 'este tema',
  'modals.report.target_user': 'este usuario',
  'modals.report.reason': 'Motivo',
  'modals.report.reason_spam': 'Spam',
  'modals.report.reason_scam': 'Estafa o fraude',
  'modals.report.reason_abuse': 'Comportamiento abusivo',
  'modals.report.reason_illegal': 'Contenido ilegal',
  'modals.report.reason_other': 'Otro',
  'modals.report.details': 'Detalles (opcional)',
  'modals.report.details_ph': 'Cualquier cosa que ayude a los moderadores a entender el problema...',
  'modals.report.submitted': 'Reporte enviado — un moderador lo revisará',
  'modals.report.failed': 'No se pudo enviar el reporte',
  'modals.report.submitting': 'Enviando…',
  'modals.report.submit': 'Enviar reporte',

  // UserListModal
  'modals.userlist.empty': 'Aún no hay nadie aquí',

  // ErrorBoundary
  'modals.error.title': 'Algo salió mal',
  'modals.error.body': 'Ocurrió un error inesperado. Intenta volver a la página de inicio.',
  'modals.error.go_home': 'Ir al inicio',

  // MarkdownToolbar
  'modals.md.bold': 'Negrita',
  'modals.md.italic': 'Cursiva',
  'modals.md.strikethrough': 'Tachado',
  'modals.md.h1': 'Encabezado 1',
  'modals.md.h2': 'Encabezado 2',
  'modals.md.inline_code': 'Código en línea',
  'modals.md.code_block': 'Bloque de código',
  'modals.md.insert_link': 'Insertar enlace',
  'modals.md.quote': 'Cita',
  'modals.md.list': 'Lista',
  'modals.md.upload_image': 'Subir imagen',
  'modals.md.invalid_url': 'Introduce una URL válida',
  'modals.md.upload_failed': 'Error al subir la imagen',
  'modals.md.link_text_ph': 'Texto del enlace (opcional)',
  'modals.md.insert': 'Insertar',

  // BannerRows
  'modals.banner.learn_more': 'Más información',
}
