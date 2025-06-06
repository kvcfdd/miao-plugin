import { App } from '#miao'
import Strategy from './wiki/Strategy.js'

let app = App.init({
  id: 'wiki',
  name: '角色攻略',
  priority: -100
})
app.reg({
  Strategy: {
    rule: '^#喵喵攻略$',
    check: Strategy.check,
    fn: Strategy.strategy
  }
})

export default app
