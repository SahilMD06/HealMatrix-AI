import { Component } from 'react'

import ServerError from '@/pages/errors/ServerError'

/**
 * Class components are the only way React lets you catch render errors —
 * there is no hook equivalent. Wraps the whole router so a bug in any one
 * page shows the 500 page instead of a blank white screen.
 */
export class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Unhandled render error:', error, info?.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <ServerError
          detail={this.state.error.message}
          onReset={() => this.setState({ error: null })}
        />
      )
    }
    return this.props.children
  }
}
