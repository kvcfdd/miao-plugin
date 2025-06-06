import fs from "node:fs"
import { Character } from "#miao.models"
import { miaoPath } from "#miao.path"

const strategyReg = /^(?:#|星铁)?(.*)(攻略|功略)$/

const Strategy = {
  check(e) {
    let msg = e.original_msg || e.msg
    if (!e.msg) return false
    e.game = /星铁/.test(e.msg) ? "sr" : e.game ?? "gs"

    let ret = strategyReg.exec(msg)
    if (!ret || !ret[1]) return false

    let char = Character.get(ret[1], e.game)
    if (!char) return false

    e.msg = "#喵喵攻略"
    e.char = char
    return true
  },

  async strategy(e) {
    let char = e.char
    if (!fs.existsSync(`${miaoPath}/resources/meta-${char.game}/info/strategy`)) {
      e.msg = e.original_msg
      return false
    }
    let { game, name, elemName, weapon } = char.getData("game,name,elemName,weapon")
    name = char.isTraveler ? "旅行者" : char.isTrailblazer ? "开拓者" : name
    let type = game == "gs" ? elemName : weapon

    let imgDir = `${miaoPath}/resources/meta-${game}/info/strategy/${type}/${name}/`
    if (fs.existsSync(imgDir)) {
      let files = fs.readdirSync(imgDir)
        .filter(f => /\.webp$/i.test(f))
        .sort((a, b) => {
          let na = parseInt(a), nb = parseInt(b)
          if (isNaN(na) || isNaN(nb)) return a.localeCompare(b)
          return na - nb
        })
      if (files.length > 0) {
        let msglist = []
        msglist.push({
          nickname: "小助手",
          message: [ `${name}攻略` ]
        })
        for (let file of files) {
          msglist.push({
            nickname: "小助手",
            message: [
              segment.image(`file://${imgDir}${file}`)
            ]
          })
        }
        let msg
        if (e.group?.makeForwardMsg) {
          msg = await e.group.makeForwardMsg(msglist)
        } else if (e.friend?.makeForwardMsg) {
          msg = await e.friend.makeForwardMsg(msglist)
        } else {
          msg = await Bot.makeForwardMsg(msglist)
        }
        return e.reply(msg)
      } else {
        e.msg = e.original_msg
        return false
      }
    } else {
      e.msg = e.original_msg
      return false
    }
  }
}

export default Strategy
