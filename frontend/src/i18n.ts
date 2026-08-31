import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

const resources = {
  en: { translation: {
    appName: 'NexaWorks', appSubtitle: 'Decision Support',
    nav: { dashboard: 'Dashboard', scenarios: 'Scenarios', plan: 'Plan', cashFlow: 'Cash flow', comparison: 'Comparison', explanations: 'Explanations' },
    header: { workspace: 'Decision workspace', language: 'Language', openMenu: 'Open navigation', closeMenu: 'Close navigation' },
    dashboard: {
      eyebrow: 'Operational overview', title: 'Decision dashboard', description: 'Live baseline context from the NexaWorks decision engine.',
      backend: 'Backend', connected: 'Connected', people: 'People', workItems: 'Work items', horizon: 'Planning horizon',
      startingCash: 'Starting cash', buffer: 'Minimum buffer', capacity: 'Team capacity', mandatory: 'Mandatory work', hours: '{{value}} hours',
    },
    async: { loading: 'Loading baseline data…', errorTitle: 'Unable to load the dashboard', retry: 'Try again' },
    placeholder: { eyebrow: 'Phase 5A foundation', description: 'This workspace is ready for the next product increment. No simulated data is shown.' },
    footer: { baseline: 'Baseline', version: 'Version {{version}}' },
  } },
  ja: { translation: {
    appName: 'NexaWorks', appSubtitle: '意思決定支援',
    nav: { dashboard: 'ダッシュボード', scenarios: 'シナリオ', plan: '計画', cashFlow: 'キャッシュフロー', comparison: '比較', explanations: '説明' },
    header: { workspace: '意思決定ワークスペース', language: '言語', openMenu: 'ナビゲーションを開く', closeMenu: 'ナビゲーションを閉じる' },
    dashboard: {
      eyebrow: '業務概要', title: '意思決定ダッシュボード', description: 'NexaWorks 意思決定エンジンのベースライン情報です。',
      backend: 'バックエンド', connected: '接続済み', people: 'メンバー', workItems: '作業項目', horizon: '計画期間',
      startingCash: '開始時現金', buffer: '最低バッファ', capacity: 'チーム工数', mandatory: '必須作業', hours: '{{value}} 時間',
    },
    async: { loading: 'ベースラインを読み込み中…', errorTitle: 'ダッシュボードを読み込めません', retry: '再試行' },
    placeholder: { eyebrow: 'Phase 5A 基盤', description: '次のプロダクト段階のための画面です。ダミーデータは表示しません。' },
    footer: { baseline: 'ベースライン', version: 'バージョン {{version}}' },
  } },
  vi: { translation: {
    appName: 'NexaWorks', appSubtitle: 'Hỗ trợ quyết định',
    nav: { dashboard: 'Tổng quan', scenarios: 'Kịch bản', plan: 'Kế hoạch', cashFlow: 'Dòng tiền', comparison: 'So sánh', explanations: 'Giải thích' },
    header: { workspace: 'Không gian quyết định', language: 'Ngôn ngữ', openMenu: 'Mở điều hướng', closeMenu: 'Đóng điều hướng' },
    dashboard: {
      eyebrow: 'Tổng quan vận hành', title: 'Bảng điều khiển quyết định', description: 'Dữ liệu nền trực tiếp từ bộ máy quyết định NexaWorks.',
      backend: 'Backend', connected: 'Đã kết nối', people: 'Nhân sự', workItems: 'Hạng mục', horizon: 'Kỳ lập kế hoạch',
      startingCash: 'Tiền mặt đầu kỳ', buffer: 'Mức đệm tối thiểu', capacity: 'Năng lực đội ngũ', mandatory: 'Công việc bắt buộc', hours: '{{value}} giờ',
    },
    async: { loading: 'Đang tải dữ liệu nền…', errorTitle: 'Không thể tải bảng điều khiển', retry: 'Thử lại' },
    placeholder: { eyebrow: 'Nền tảng Phase 5A', description: 'Khu vực này đã sẵn sàng cho bước phát triển tiếp theo. Không hiển thị dữ liệu giả.' },
    footer: { baseline: 'Dữ liệu nền', version: 'Phiên bản {{version}}' },
  } },
} as const

void i18n.use(initReactI18next).init({
  resources,
  lng: 'en',
  fallbackLng: 'en',
  showSupportNotice: false,
  interpolation: { escapeValue: false },
})

export default i18n
