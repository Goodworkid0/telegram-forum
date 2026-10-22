// Merged zh dictionary. Each domain file owns the strings for one area of
// the app so work on different pages never touches the same file.
import common from './common'
import settings from './settings'
import forum from './forum'
import shop from './shop'
import messages from './messages'
import social from './social'
import escrow from './escrow'
import files from './files'
import modals from './modals'

export default {
  ...common,
  ...settings,
  ...forum,
  ...shop,
  ...messages,
  ...social,
  ...escrow,
  ...files,
  ...modals,
}
