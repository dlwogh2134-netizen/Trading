const DEFAULT_EDITOR_STATE = {
  base_symbol: '',
  display_name_ko: '',
  display_name_en: '',
  aliases: '',
  default_exchange: 'COINONE',
  is_visible: true,
  admin_trading_blocked: false,
  admin_block_reason: '',
  admin_note: '',
  coinone_symbol: '',
  binance_symbol: '',
}

export function buildCryptoEditorState(item) {
  return {
    ...DEFAULT_EDITOR_STATE,
    base_symbol: item.base_symbol,
    display_name_ko: item.display_name_ko || '',
    display_name_en: item.display_name_en || '',
    aliases: Array.isArray(item.aliases) ? item.aliases.join(', ') : '',
    default_exchange: item.default_exchange || 'COINONE',
    is_visible: item.is_visible !== false,
    admin_trading_blocked: Boolean(item.admin_trading_blocked),
    admin_block_reason: item.admin_block_reason || '',
    admin_note: item.admin_note || '',
    coinone_symbol: item.coinone_symbol || '',
    binance_symbol: item.binance_symbol || '',
  }
}
