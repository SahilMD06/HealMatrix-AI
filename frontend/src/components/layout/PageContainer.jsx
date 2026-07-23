import { useOutletContext } from 'react-router-dom'
import { motion } from 'framer-motion'

import { Header } from './Header'

/** Standard page frame: header plus a scrollable, animated content column. */
export function PageContainer({ title, subtitle, actions, children }) {
  const { openMenu, openSearch } = useOutletContext()
  return (
    <>
      <Header
        title={title}
        subtitle={subtitle}
        onMenuClick={openMenu}
        onSearchClick={openSearch}
        actions={actions}
      />
      <motion.main
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28 }}
        className="flex-1 overflow-y-auto scrollbar-slim p-4 lg:p-6"
      >
        <div className="mx-auto max-w-[1440px]">{children}</div>
      </motion.main>
    </>
  )
}
