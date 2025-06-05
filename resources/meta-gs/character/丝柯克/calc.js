export const details = [{
  title: '单人大招单段(直伤)',
  dmg: ({ talent }, dmg) => dmg(talent.q['斩击伤害2'][0], 'q')
}, {
  title: '单人大招最终段(直伤)',
  dmg: ({ talent }, dmg) => dmg(talent.q['斩击最终段伤害'], 'q')
}, {
  title: '单人大招最终段融化',
  dmg: ({ talent }, dmg) => dmg(talent.q['斩击最终段伤害'], 'q', 'melt')
}, {
  title: '单人大招总伤(直伤)',
  dmg: ({ talent }, dmg) => dmg(talent.q['斩击伤害'] + talent.q['斩击最终段伤害'], 'q')
}]

export const defDmgIdx = 2
export const mainAttr = 'atk,cpct,cdmg'

export const buffs = [{
  title: '蛇之狡谋加成：伤害提升[qPlus]点',
  data: {
    qPlus: ({ cons, attr, calc, talent }) => calc(attr.atk) * talent.q['蛇之狡谋加成'] / 100 * cons < 1 ? 22 : 12
  }
}, {
  title: '二命：攻击力提升[atkPct]%',
  cons: 2,
  data: {
    atkPct: 70
  }
}, 'melt']
