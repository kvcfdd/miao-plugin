import fs from 'node:fs'
import lodash from 'lodash'
import { exec } from 'child_process'
import { Cfg, Common, Data, Version, App } from '#miao'
import makemsg from '../../../lib/common/common.js'
import { execSync } from 'child_process'
import fetch from 'node-fetch'
import { miaoPath } from '#miao.path'
import schedule from 'node-schedule'

let keys = lodash.map(Cfg.getCfgSchemaMap(), (i) => i.key)
let app = App.init({
  id: 'admin',
  name: '喵喵设置',
  desc: '喵喵设置'
})

let sysCfgReg = new RegExp(`^#喵喵设置\\s*(${keys.join('|')})?\\s*(.*)$`)

app.reg({
  updateRes: {
    rule: /^#喵喵(强制)?(更新图像|图像更新)$/,
    fn: updateRes,
    desc: '【#管理】更新素材'
  },
  updateStrategy: {
    rule: /^#喵喵(安装|(强制)?更新)攻略资源$/,
    fn: updateStrategy,
    desc: '【#管理】攻略资源'
  },
  update: {
    rule: /^#喵喵(强制)?更新$/,
    fn: updateMiaoPlugin,
    desc: '【#管理】喵喵更新'
  },
  updatelog: {
    rule: /^#?喵喵更新日志$/,
    fn: Miaoupdatelog,
    desc: '【#管理】喵喵更新'
  },
  sysCfg: {
    rule: sysCfgReg,
    fn: sysCfg,
    desc: '【#管理】系统设置'
  },
  miaoApiInfo: {
    rule: /^#喵喵api$/,
    fn: miaoApiInfo,
    desc: '【#管理】喵喵Api'
  }
})

export default app

const resPath = `${miaoPath}/resources/`
const plusPath = `${resPath}/miao-res-plus/`

const checkAuth = async function (e) {
  if (!e.isMaster) {
    e.reply(`只有主人才能命令喵喵哦~
    (*/ω＼*)`)
    return false
  }
  return true
}

async function sysCfg (e) {
  if (!await checkAuth(e)) {
    return true
  }

  let cfgReg = sysCfgReg
  let regRet = cfgReg.exec(e.msg)
  let cfgSchemaMap = Cfg.getCfgSchemaMap()

  if (!regRet) {
    return true
  }

  if (regRet[1]) {
    // 设置模式
    let val = regRet[2] || ''

    let cfgSchema = cfgSchemaMap[regRet[1]]
    if (cfgSchema.input) {
      val = cfgSchema.input(val)
    } else if (cfgSchema.type === 'str') {
      val = (val || cfgSchema.def) + ''
    } else {
      val = cfgSchema.type === 'num' ? (val * 1 || cfgSchema.def) : !/关闭/.test(val)
    }
    Cfg.set(cfgSchema.cfgKey, val)
  }

  let schema = Cfg.getCfgSchema()
  let cfg = Cfg.getCfg()
  let imgPlus = fs.existsSync(plusPath)

  // 渲染图像
  return await Common.render('admin/index', {
    schema,
    cfg,
    imgPlus,
    isMiao: Version.isMiao
  }, { e, scale: 1.4 })
}

async function updateRes (e) {
  if (!await checkAuth(e)) {
    return true
  }
  let isForce = e.msg.includes('强制')
  let command = ''
  if (fs.existsSync(`${resPath}/miao-res-plus/`)) {
    e.reply('开始尝试更新，请耐心等待~')
    command = 'git pull'
    if (isForce) {
      command = 'git  checkout . && git  pull'
    }
    exec(command, { cwd: `${resPath}/miao-res-plus/` }, function (error, stdout, stderr) {
      if (/(Already up[ -]to[ -]date|已经是最新的)/.test(stdout)) {
        e.reply('目前所有图片都已经是最新了~')
        return true
      }
      let numRet = /(\d*) files changed,/.exec(stdout)
      if (numRet && numRet[1]) {
        e.reply(`报告主人，更新成功，此次更新了${numRet[1]}个图片~`)
        return true
      }
      if (error) {
        e.reply('更新失败！\nError code: ' + error.code + '\n' + error.stack + '\n 请稍后重试。')
      } else {
        e.reply('图片加量包更新成功~')
      }
    })
  } else {
    command = `git clone https://ww-github.qyxc.org/kvcfdd/miao-res-plus.git "${resPath}/miao-res-plus/" --depth=1`
    e.reply('开始尝试安装图片加量包，可能会需要一段时间，请耐心等待~')
    exec(command, function (error, stdout, stderr) {
      if (error) {
        e.reply('角色图片加量包安装失败！\nError code: ' + error.code + '\n' + error.stack + '\n 请稍后重试。')
      } else {
        e.reply('角色图片加量包安装成功！')
      }
    })
  }
  return true
}

async function updateStrategy(e) {
  if (!await checkAuth(e)) return true
  let games = [ "gs", "sr" ]

  for (let game of games) {
    let command = ""
    let path = `${resPath}/meta-${game}/info/strategy/`
    if (fs.existsSync(path)) {
      await e.reply(`[喵喵角色攻略-${game}] 开始尝试更新攻略资源包，请稍后~`)
      command = "git pull"
      if (e.msg.includes("强制")) command = "git  checkout . && git  pull"

      await new Promise((resolve) => {
        exec(command, { cwd: path }, async function(error, stdout, stderr) {
          if (/(Already up[ -]to[ -]date|已经是最新的)/.test(stdout)) {
            await e.reply(`[喵喵角色攻略-${game}] 已经是最新了~`)
            return resolve()
          }
          let numRet = /(\d*) files changed,/.exec(stdout)
          if (numRet && numRet[1]) {
            await e.reply(`[喵喵角色攻略-${game}] 报告主人，更新成功，此次改动了${numRet[1]}个文件~`)
            return resolve()
          }
          if (error) {
            await e.reply(`[喵喵角色攻略-${game}] 更新失败！\nError code: ${error.code}\n${error.stack}\n 请稍后重试。`)
          } else {
            await e.reply(`[喵喵角色攻略-${game}] 攻略资源更新成功！`)
          }
          resolve()
        })
      })
    } else {
      command = `git clone https://ww-github.qyxc.org/kvcfdd/${game}.git "${path}" --depth=1`
      await e.reply(`[喵喵角色攻略-${game}] 开始尝试安装攻略资源包，请稍后~`)
      await new Promise((resolve) => {
        exec(command, async function(error, stdout, stderr) {
          if (error) {
            await e.reply(`[喵喵角色攻略-${game}] 攻略资源包安装失败！\nError code: ${error.code}\n${error.stack}\n 请稍后重试。`)
          } else {
            await e.reply(`[喵喵角色攻略-${game}] 攻略资源包安装成功！`)
          }
          resolve()
        })
      })
    }
  }
  return true
}

let timer

async function updateMiaoPlugin (e) {
  if (!await checkAuth(e)) {
    return true
  }
  let isForce = e.msg.includes('强制')
  let command = 'git  pull'
  if (isForce) {
    command = 'git  checkout . && git  pull'
    e.reply('正在执行强制更新操作，请稍等')
  } else {
    e.reply('正在执行更新操作，请稍等')
  }
  exec(command, { cwd: miaoPath }, function (error, stdout, stderr) {
    if (/(Already up[ -]to[ -]date|已经是最新的)/.test(stdout)) {
      e.reply('目前已经是最新版喵喵了~')
      return true
    }
    if (error) {
      e.reply('喵喵更新失败！\nError code: ' + error.code + '\n' + error.stack + '\n 请稍后重试。')
      return true
    }
    e.reply('喵喵更新成功，正在尝试重新启动Yunzai以应用更新...')
    timer && clearTimeout(timer)
    Data.setCacheJSON('miao:restart-msg', {
      msg: '重启成功，新版喵喵已经生效',
      qq: e.user_id
    }, 30)
    timer = setTimeout(function () {
      let command = 'npm run start'
      if (process.argv[1].includes('pm2')) {
        command = 'npm run restart'
      }
      exec(command, function (error, stdout, stderr) {
        if (error) {
          e.reply('自动重启失败，请手动重启以应用新版喵喵。\nError code: ' + error.code + '\n' + error.stack + '\n')
          Bot.logger.error(`重启失败\n${error.stack}`)
          return true
        } else if (stdout) {
          Bot.logger.mark('重启成功，运行已转为后台，查看日志请用命令：npm run log')
          Bot.logger.mark('停止后台运行命令：npm stop')
          process.exit()
        }
      })
    }, 1000)
  })
  return true
}

async function Miaoupdatelog (e, plugin = 'miao-plugin') {
  let cm = 'git log  -20 --oneline --pretty=format:"%h||[%cd]  %s" --date=format:"%F %T"'
  if (plugin) {
    cm = `cd ./plugins/${plugin}/ && ${cm}`
  }
  let logAll
  try {
    logAll = await execSync(cm, { encoding: 'utf-8', windowsHide: true })
  } catch (error) {
    logger.error(error.toString())
    this.reply(error.toString())
  }
  if (!logAll) return false
  logAll = logAll.split('\n')
  let log = []
  for (let str of logAll) {
    str = str.split('||')
    if (str[0] == this.oldCommitId) break
    if (str[1].includes('Merge branch')) continue
    log.push(str[1])
  }
  let line = log.length
  log = log.join('\n\n')
  if (log.length <= 0) return ''
  let end = '更多详细信息，请前往github查看\nhttps://github.com/kvcfdd/miao-plugin'
  log = await makemsg.makeForwardMsg(this.e, [log, end], `${plugin}更新日志，共${line}条`)
  e.reply(log)
}

async function miaoApiInfo (e) {
  if (!await checkAuth(e)) {
    return true
  }
  let { diyCfg } = await Data.importCfg('profile')
  let { qq, token } = (diyCfg?.miaoApi || {})
  if (!qq || !token) {
    return e.reply('未正确填写miaoApi token，请检查miao-plugin/config/profile.js文件')
  }
  if (token.length !== 32) {
    return e.reply('miaoApi token格式错误')
  }
  let req = await fetch(`http://miao.games/api/info?qq=${qq}&token=${token}`)
  let data = await req.json()
  if (data.status !== 0) {
    return e.reply('token检查错误，请求失败')
  }
  e.reply(data.msg)
}

async function autoUpdateStrategy() {
  logger.mark('[喵喵自动任务] 检查资源更新...')
  try {
    if (fs.existsSync(`${resPath}/miao-res-plus/`)) {
      logger.mark('[图片加量包] 检查更新')
      const { stdout: imgStdout } = await new Promise((resolve, reject) => {
        exec("git pull", { cwd: `${resPath}/miao-res-plus/` }, (error, stdout, stderr) => {
          if (error) {
            reject(error)
            return
          }
          resolve({ stdout, stderr })
        })
      })
      if (/(Already up[ -]to[ -]date|已经是最新的)/.test(imgStdout)) {
        logger.mark('[图片加量包] 已是最新')
      } else {
        logger.mark('[图片加量包] 已更新')
      }
    } else {
      logger.mark('[图片加量包] 未安装')
    }
  } catch (error) {
    logger.error(`[图片加量包] 更新失败: ${error.message || error}`)
  }

  try {
    const profilePath = `${resPath}/profile`
    const profileGitPath = `${profilePath}/.git`
    if (fs.existsSync(profilePath) && fs.existsSync(profileGitPath)) {
      logger.mark('[profile资源] 检查更新')
      const { stdout: profileStdout } = await new Promise((resolve, reject) => {
        exec("git pull", { cwd: profilePath }, (error, stdout, stderr) => {
          if (error) {
            reject(error)
            return
          }
          resolve({ stdout, stderr })
        })
      })
      if (/(Already up[ -]to[ -]date|已经是最新的)/.test(profileStdout)) {
        logger.mark('[profile资源] 已是最新')
      } else {
        logger.mark('[profile资源] 已更新')
      }
    } else {
      logger.mark('[profile资源] 非git资源')
    }
  } catch (error) {
    logger.error(`[profile资源] 更新失败: ${error.message || error}`)
  }

  const games = ["gs", "sr"]
  for (let game of games) {
    let path = `${resPath}/meta-${game}/info/strategy/`
    try {
      if (fs.existsSync(path)) {
        logger.mark(`[${game}攻略] 检查更新`)
        const { stdout } = await new Promise((resolve, reject) => {
          exec("git pull", { cwd: path }, (error, stdout, stderr) => {
            if (error) {
              reject(error)
              return
            }
            resolve({ stdout, stderr })
          })
        })
        if (/(Already up[ -]to[ -]date|已经是最新的)/.test(stdout)) {
          logger.mark(`[${game}攻略] 已是最新`)
        } else {
          logger.mark(`[${game}攻略] 已更新`)
        }
      } else {
        logger.mark(`[${game}攻略] 未安装`)
      }
    } catch (error) {
      logger.error(`[${game}攻略] 更新失败: ${error.message || error}`)
    }
  }
}

const scheduleTask = () => {
  schedule.scheduleJob('0 30 0 * * *', async () => {
    try {
      await autoUpdateStrategy()
    } catch (e) {
      logger.error(`[喵喵自动任务] 定时任务执行失败: ${e.message || e}`)
    }
  })
}

scheduleTask()