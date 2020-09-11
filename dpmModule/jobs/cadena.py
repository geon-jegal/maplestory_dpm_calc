from ..kernel import core
from ..kernel.core import VSkillModifier as V
from ..character import characterKernel as ck
from functools import partial
from ..status.ability import Ability_tool
from . import globalSkill
from .jobbranch import thieves
from math import ceil

#TODO : 5차 신스킬 적용
######   Passive Skill   ######

class WeaponVarietyStackWrapper(core.StackSkillWrapper): # TODO: 굳이 관리할 필요 없이 항상 최대 스택 가정해도 되지 않을까?
    def __init__(self, _max, prof_agent, final_attack, use_prof_agent_attack):
        super(WeaponVarietyStackWrapper, self).__init__(core.BuffSkill("웨폰 버라이어티 스택", 0, 99999999), _max)
        self.stackLog = []
        self.currentWeapon = None
        self.use_final_attack = core.OptionalElement(final_attack.is_available, final_attack, name = "웨폰 버라이어티 쿨타임")
        self.use_prof_agent_attack = use_prof_agent_attack
        self.prof_agent = prof_agent
        self.modifierInvariantFlag = False
        
    def vary(self, weapon):
        if weapon not in self.stackLog:
            self.stackLog.append(weapon)
        
        self.currentWeapon = weapon
            
        return core.ResultObject(0, core.CharacterModifier(), 0, 0, sname = self.skill.name, spec = 'graph control')
    
    def get_modifier(self):
        multiplier = 11
        if self.prof_agent.is_active():
            multiplier *= 2
        return core.CharacterModifier(pdamage_indep = len(self.stackLog) * multiplier)

    def _changed(self, weapon):
        return self.currentWeapon != weapon
    
    def stackController(self, weapon):
        task = core.Task(self, partial(self.vary, weapon))
        taskHolder = core.TaskHolder(task, name = "웨버 스택")
        taskHolder.onAfter(self.use_final_attack)
        taskHolder.onAfter(self.use_prof_agent_attack)
        conditionalTask = core.OptionalElement(partial(self._changed, weapon), taskHolder, name = "무기 교체")
        return conditionalTask

class MaelstromWrapper(core.SummonSkillWrapper):
    def __init__(self, vEhc, tick):
        self.tick_list = [840, 120, 180, 270, 390, 540, 720, 930, 1170, 1440, 1740, 99999999]
        self.currentTick = len(self.tick_list)
        self.reuseTick = tick
        skill = core.SummonSkill("체인아츠:메일스트롬", 540, 0, 300+12*vEhc.getV(3,2), 4, 8540).isV(vEhc,3,2)
        super(MaelstromWrapper, self).__init__(skill)

    def check_use(self):
        return self.currentTick >= self.reuseTick

    def _use(self, skill_modifier):
        result = super(MaelstromWrapper, self)._use(skill_modifier)
        self.currentTick = 0
        self.tick = self.tick_list[0]
        self.currentTick += 1
        return result

    def _useTick(self):
        if self.onoff and self.tick <= 0:
            self.tick += self.tick_list[self.currentTick]
            self.currentTick += 1
            return core.ResultObject(0, self.get_modifier(), self.skill.damage, self.skill.hit, sname = self.skill.name, spec = self.skill.spec)
        else:
            return core.ResultObject(0, self.disabledModifier, 0, 0, sname = self.skill.name, spec = self.skill.spec)    

class JobGenerator(ck.JobGenerator):
    def __init__(self):
        super(JobGenerator, self).__init__()
        self.vEnhanceNum = 11
        self.jobtype = "luk"
        self.jobname = "카데나"
        self.ability_list = Ability_tool.get_ability_set('boss_pdamage', 'reuse', 'mess') # 임시로 보공 첫줄 사용, 재사용 구현시 변경
        self.preEmptiveSkills = 1
        
    def get_passive_skill_list(self, vEhc, chtr : ck.AbstractCharacter):
        passive_level = chtr.get_base_modifier().passive_level + self.combat
        CollectingForLeap = core.InformedCharacterModifier("콜렉팅 포리프", stat_main = 50)
        
        PhisicalTraining = core.InformedCharacterModifier("피지컬 트레이닝", stat_main = 30, stat_sub = 30)
        QuickserviceMind = core.InformedCharacterModifier("퀵서비스 마인드", att = 10, crit_damage = 5, crit = 10)
        
        BasicDetection = core.InformedCharacterModifier("베이직 디텍션", armor_ignore = 20)
        
        WeaponMastery = core.InformedCharacterModifier("웨폰 엑스퍼트", att = 30 + passive_level, crit = 30 + passive_level, crit_damage = 15 + ceil(passive_level / 2))
        QuickserviceMind_II = core.InformedCharacterModifier("퀵서비스 마인드 II", att = 30, crit_damage = 5, crit = 10)
        ReadyToDiePassive = thieves.ReadyToDiePassiveWrapper(vEhc, 2, 3)
        
        return [CollectingForLeap, PhisicalTraining,
                                    QuickserviceMind, BasicDetection, WeaponMastery, QuickserviceMind_II, ReadyToDiePassive]

    def get_modifier_optimization_hint(self):
        return core.CharacterModifier(armor_ignore = 30, crit_damage = 40, pdamage = 20, crit = 6)
                              
    def get_not_implied_skill_list(self, vEhc, chtr : ck.AbstractCharacter):
        passive_level = chtr.get_base_modifier().passive_level + self.combat
        WeaponConstant = core.InformedCharacterModifier("무기상수",pdamage_indep = 30)
        Mastery = core.InformedCharacterModifier("숙련도",pdamage_indep = -5 + 0.5 * ceil(passive_level / 2))
        
        return [WeaponConstant, Mastery]		                      

    def generate(self, vEhc, chtr : ck.AbstractCharacter):
        '''
        논체인아츠-리인포스, 보스킬러
        체인아츠스트로크-넥스트어택 리인포스, 리인포스
        
        체인아츠:테이크다운-쿨타임 리듀스
        
        코강순서:
        스트로크,버라이어티,허슬 - 니들배트 - 브릭 - 샷건/봄 - 크러시/에이전트 - 시미터/클로 - 나이프/윙대거 - 테이크다운
        
        스킬강화순서:
        퓨리-오드-버스트-멜-레투다
        
        1타캔슬 120ms
        캔슬 180ms
        
        서먼 스로잉 윙대거 3타 후 폭발
        
        시미터, 샷건, 나이프, 브릭, 니들배트 1타, 윙대거 1틱은 최종뎀 15%를 받고 있음.
        
        봄-브릭 / 샷건-클로 / 나이프 / 윙대거 / 배트 / 시미터-체이스 / 메일스트롬 4초당 1회 
        '''
        STROKE1_HIT_RATE = 1
        STROKE1_CANCEL_TIME = 120
        CANCEL_TIME = 180
        WINGDAGGER_HIT = 3

        passive_level = chtr.get_base_modifier().passive_level + self.combat
        CheapShotII = core.CharacterModifier(crit = 2, crit_damage = 10 + ceil(passive_level / 4)) # 위크포인트 컨버징 어택
        CheapShotIIBleed = core.DotSkill("위크포인트 컨버징 어택(출혈)", 0, 1000, 110 + 2 * passive_level, 1, 99999999).wrap(core.SummonSkillWrapper)
        CheapShotIIBleedBuff = core.BuffSkill("위크포인트 컨버징 어택(출혈)(디버프)", 0, 99999999, crit = CheapShotII.crit, crit_damage = CheapShotII.crit_damage).wrap(core.BuffSkillWrapper)
        CheapShotIIAdventureMageBuff = core.BuffSkill("위크포인트 컨버징 어택(모법링크)", 0, 99999999, crit = CheapShotII.crit, crit_damage = CheapShotII.crit_damage).wrap(core.BuffSkillWrapper)

        #버프
        Booster = core.BuffSkill("부스터", 0, 200000).wrap(core.BuffSkillWrapper)
        SpecialPotion = core.BuffSkill("상인단 특제 비약", 570, 60*1000, pdamage = 10, crit = 10, cooltime = 120*1000).wrap(core.BuffSkillWrapper) # 카데나만 딜레이있음
        
        ProfessionalAgent = core.BuffSkill("프로페셔널 에이전트", 570, 30000, cooltime = 200000).wrap(core.BuffSkillWrapper)
        ProfessionalAgentAdditionalDamage = core.DamageSkill("프로페셔널 에이전트(공격)", 0, 255, 2).setV(vEhc, 4, 2, False).wrap(core.DamageSkillWrapper)
        ProfessionalAgent_Attack = core.OptionalElement(ProfessionalAgent.is_active, ProfessionalAgentAdditionalDamage, name= "프로페셔널 에이전트 추가타")
        
        #웨폰버라이어티 추가타	
        WeaponVarietyAttack = core.DamageSkill("웨폰 버라이어티", 0, 350 + 15 * passive_level, 4, cooltime = 250).setV(vEhc, 0, 2, False).wrap(core.DamageSkillWrapper)
        WeaponVariety = WeaponVarietyStackWrapper(11, ProfessionalAgent, WeaponVarietyAttack, ProfessionalAgent_Attack)
        
        
        #체인아츠
        ChainArts_Stroke_1 = core.DamageSkill("체인아츠:스트로크(1타)", 210, 150, 2 * STROKE1_HIT_RATE, modifier = core.CharacterModifier(pdamage = 20)).setV(vEhc, 0, 2, False).wrap(core.DamageSkillWrapper)
        ChainArts_Stroke_1_Cancel = core.DamageSkill("체인아츠:스트로크(1타)(캔슬)", STROKE1_CANCEL_TIME, 150, 2 * STROKE1_HIT_RATE, modifier = core.CharacterModifier(pdamage = 20)).setV(vEhc, 0, 2, False).wrap(core.DamageSkillWrapper)
        ChainArts_Stroke_2 = core.DamageSkill("체인아츠:스트로크(2타)", 390, 400, 5, modifier = core.CharacterModifier(pdamage = 20)).setV(vEhc, 0, 2, False).wrap(core.DamageSkillWrapper)
        ChainArts_Stroke_2_Cancel = core.DamageSkill("체인아츠:스트로크(2타)(캔슬)", CANCEL_TIME, 400, 5, modifier = core.CharacterModifier(pdamage = 20)).setV(vEhc, 0, 2, False).wrap(core.DamageSkillWrapper)
        
        ChainArts_Chais = core.DamageSkill("체인아츠:체이스", 150, 100, 1).wrap(core.DamageSkillWrapper)
        ChainArts_Crush = core.DamageSkill("체인아츠:크러시", 990, 950, 8, cooltime = 30000).setV(vEhc, 4, 2, True).wrap(core.DamageSkillWrapper) # 미사용

        #ChainArts_ToughHustleInit = core.DamageSkill("체인아츠:터프허슬", 0, 0, 0, cooltime = 50000).setV(vEhc, 0, 2, False) #지속형		
        #ChainArts_ToughHustle = core.DamageSkill("체인아츠:터프허슬", 5000000, 600 + 7 * self.combat, 2).setV(vEhc, 0, 2, False) #지속형, 6초, 미사용
        
        # TODO: 향후 딜사이클에 사용될 경우 컴뱃 오더스 적용할것
        # ChainArts_takedown = core.DamageSkill("체인아츠:테이크다운", 5360, 990, 15, cooltime = 150*1000, modifier = core.CharacterModifier(armor_ignore = 80)).setV(vEhc, 7, 2, False).wrap(core.DamageSkillWrapper)
        # ChainArts_takedown_wave = core.DamageSkill("체인아츠:테이크다운(파동)", 0, 600, 16, modifier = core.CharacterModifier(armor_ignore = 80)).setV(vEhc, 7, 2, False).wrap(core.DamageSkillWrapper)
        # ChainArts_takedown_final = core.DamageSkill("체인아츠:테이크다운(최종)", 0, 5000, 1, modifier = core.CharacterModifier(armor_ignore = 80)).setV(vEhc, 7, 2, False).wrap(core.DamageSkillWrapper)
        # ChainArts_takedown_bind = core.BuffSkill("체인아츠:테이크다운(바인드)", 0, 15000, crit = CheapShotII.crit, crit_damage = CheapShotII.crit_damage, cooltime = -1).wrap(core.BuffSkillWrapper)
        
        #논체인아츠 스킬
        
        SummonCuttingSimiter = core.DamageSkill("서먼 커팅 시미터", CANCEL_TIME, 425 + 5 * passive_level, 5, cooltime = 4000, red = True, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20, pdamage_indep = 15)).setV(vEhc, 5, 2, False).wrap(core.DamageSkillWrapper)
        SummonScratchingClaw = core.DamageSkill("서먼 스크래칭 클로", CANCEL_TIME, 455 + 5 * passive_level, 4, cooltime = 3000, red = True, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20)).setV(vEhc, 5, 2, False).wrap(core.DamageSkillWrapper)
        
        SummonThrowingWingdagger = core.DamageSkill("서먼 스로잉 윙대거", 780, 0, 0, cooltime = 10000, red = True, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20)).wrap(core.DamageSkillWrapper)
        SummonThrowingWingdaggerSummon = core.SummonSkill("서먼 스로잉 윙대거(소환)", 0, 330, 425 + 5 * passive_level, 1, 330*WINGDAGGER_HIT, cooltime= -1, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20, pdamage_indep = 15 / WINGDAGGER_HIT)).setV(vEhc, 6, 2, False).wrap(core.SummonSkillWrapper)
        SummonThrowingWingdaggerEnd = core.DamageSkill("서먼 스로잉 윙대거(폭발)", 0, 670 + 5 * passive_level, 3, cooltime = -1, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20)).setV(vEhc, 6, 2, False).wrap(core.DamageSkillWrapper)
        
        SummonShootingShotgun = core.DamageSkill("서먼 슈팅 샷건", CANCEL_TIME, 510 + 5 * passive_level, 7, cooltime = 5000, red = True, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20, pdamage_indep = 15)).setV(vEhc, 3, 2, False).wrap(core.DamageSkillWrapper)
        SummonSlachingKnife = core.DamageSkill("서먼 슬래싱 나이프", CANCEL_TIME, 435 + 5 * passive_level, 8, cooltime = 10000, red = True, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20, pdamage_indep = 15)).setV(vEhc, 6, 2, False).wrap(core.DamageSkillWrapper)
        SummonSlachingKnife_Horror = core.BuffSkill("서먼 슬래싱 나이프(공포)", 0, 10000, armor_ignore = 30, crit = CheapShotII.crit, crit_damage = CheapShotII.crit_damage, cooltime = -1).wrap(core.BuffSkillWrapper)
        
        SummonReleasingBoom = core.DamageSkill("서먼 릴리징 봄", CANCEL_TIME, 535 + 5 * passive_level, 6, cooltime = 8000, red = True, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20)).setV(vEhc, 3, 2, False).wrap(core.DamageSkillWrapper)
        SummonStrikingBrick = core.DamageSkill("서먼 스트라이킹 브릭", CANCEL_TIME, 485 + 8*self.combat, 7, cooltime = 8000, red = True, modifier = core.CharacterModifier(boss_pdamage = 20, pdamage = 20, pdamage_indep = 15)).setV(vEhc, 2, 2, False).wrap(core.DamageSkillWrapper)
        SummonBeatingNeedlebat_1 = core.DamageSkill("서먼 비팅 니들배트(1타)", 360, 450 + 10 * self.combat, 6, modifier = core.CharacterModifier(pdamage = 40 + 20, boss_pdamage = 20, pdamage_indep = 15), cooltime = 12000, red = True).setV(vEhc, 1, 2, False).wrap(core.DamageSkillWrapper)
        SummonBeatingNeedlebat_2 = core.DamageSkill("서먼 비팅 니들배트(2타)", 420, 555 + 10 * self.combat, 7, modifier = core.CharacterModifier(pdamage = 40 + 20, boss_pdamage = 20)).setV(vEhc, 1, 2, False).wrap(core.DamageSkillWrapper)
        SummonBeatingNeedlebat_3 = core.DamageSkill("서먼 비팅 니들배트(3타)", CANCEL_TIME, 715 + 10 * self.combat, 8, modifier = core.CharacterModifier(pdamage = 50 + 20, boss_pdamage = 20)).setV(vEhc, 1, 2, False).wrap(core.DamageSkillWrapper)
        SummonBeatingNeedlebat_Honmy = core.BuffSkill("서먼 비팅 니들배트(혼미)", 0, 15000, crit = CheapShotII.crit, crit_damage = CheapShotII.crit_damage, cooltime = -1).wrap(core.BuffSkillWrapper)
        
        VenomBurst = core.DotSkill("베놈 버스트", 0, 1000, 160+6*vEhc.getV(4,4), 1, 99999999).isV(vEhc,4,4).wrap(core.SummonSkillWrapper)
        VenomBurst_Poison = core.BuffSkill("베놈 버스트(중독)", 0, 99999999, crit = CheapShotII.crit, crit_damage = CheapShotII.crit_damage, cooltime = -1).isV(vEhc,4,4).wrap(core.BuffSkillWrapper)
        
        ReadyToDie = thieves.ReadyToDieWrapper(vEhc, 2, 3)
        
        ChainArts_Fury = core.BuffSkill("체인아츠:퓨리", 420, (35+vEhc.getV(0,0))*1000, cooltime = (180-vEhc.getV(0,0))*1000, red = True).isV(vEhc,0,0).wrap(core.BuffSkillWrapper)
        ChainArts_Fury_Damage = core.DamageSkill("체인아츠:퓨리(공격)", 0, 250+10*vEhc.getV(0,0), 6, cooltime = 600).isV(vEhc,0,0).wrap(core.DamageSkillWrapper)
        
        AD_Odnunce = core.SummonSkill("A.D 오드넌스", 360, 270, 225+9*vEhc.getV(1,1), 5, 10000, cooltime = 25000, red = True).isV(vEhc,1,1).wrap(core.SummonSkillWrapper) # 37*5타
        AD_Odnunce_Final = core.DamageSkill("A.D 오드넌스(막타)", 0, 750+30*vEhc.getV(1,1), 8, cooltime = -1).isV(vEhc,1,1).wrap(core.DamageSkillWrapper)
        
        ChainArts_Maelstorm = MaelstromWrapper(vEhc, 8)
        ChainArts_Maelstorm_Slow = core.BuffSkill("체인아츠:메일스트롬(중독)", 0, 4000+6000, crit = CheapShotII.crit, crit_damage = CheapShotII.crit_damage, cooltime = -1).isV(vEhc,3,2).wrap(core.BuffSkillWrapper)
        ######   Skill Wrapper   ######

        #기본 연계 연결
        #ChainArts_ToughHustleInit.onAfter(ChainArts_ToughHustle) 터프허슬 미사용
        # ChainArts_takedown.onAfter(ChainArts_takedown_bind)
        # ChainArts_takedown_bind.onAfters([ChainArts_takedown_wave, ChainArts_takedown_final])
        
        SummonThrowingWingdagger.onAfter(SummonThrowingWingdaggerSummon)
        SummonThrowingWingdaggerSummon.onAfter(SummonThrowingWingdaggerEnd.controller(330*WINGDAGGER_HIT))
        
        SummonSlachingKnife.onAfter(SummonSlachingKnife_Horror)
        
        VenomBurst.onAfter(VenomBurst_Poison)
        
        ChainArts_Fury_Use = core.OptionalElement(lambda : ChainArts_Fury_Damage.is_available() and ChainArts_Fury.is_active(), ChainArts_Fury_Damage, name = "체인아츠:퓨리 발동조건")
        
        AD_Odnunce.onAfter(AD_Odnunce_Final.controller(10000))
        ChainArts_Maelstorm.onAfter(ChainArts_Maelstorm_Slow)


        # 웨폰 버라이어티 호출
        SummonCuttingSimiter.onAfter(WeaponVariety.stackController("시미터"))
        SummonScratchingClaw.onAfter(WeaponVariety.stackController("클로"))
        SummonThrowingWingdaggerSummon.onTick(WeaponVariety.stackController("윙대거"))
        SummonThrowingWingdaggerEnd.onAfter(WeaponVariety.stackController("윙대거"))
        
        SummonShootingShotgun.onAfter(WeaponVariety.stackController("샷건"))
        SummonSlachingKnife.onAfter(WeaponVariety.stackController("나이프"))
        SummonReleasingBoom.onAfter(WeaponVariety.stackController("봄"))
        SummonStrikingBrick.onAfter(WeaponVariety.stackController("브릭"))

        SummonBeatingNeedlebat_1.onAfter(WeaponVariety.stackController("배트"))
        SummonBeatingNeedlebat_1.onAfter(SummonBeatingNeedlebat_2)
        SummonBeatingNeedlebat_2.onAfter(WeaponVariety.stackController("배트"))
        SummonBeatingNeedlebat_2.onAfter(SummonBeatingNeedlebat_3)
        SummonBeatingNeedlebat_3.onAfter(WeaponVariety.stackController("배트"))
        SummonBeatingNeedlebat_3.onAfter(SummonBeatingNeedlebat_Honmy)
        
        #카데나 딜 사이클들.
        
        #샷건-클로
        ShootgunClawCombo = core.DamageSkill('샷건-클로', 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1_Cancel, SummonShootingShotgun, ChainArts_Stroke_1, ChainArts_Stroke_2_Cancel, SummonScratchingClaw]:
            ShootgunClawCombo.onAfter(i)
        
        for c in [core.ConstraintElement('샷건', SummonShootingShotgun, SummonShootingShotgun.is_available),
                    core.ConstraintElement('클로', SummonScratchingClaw, SummonScratchingClaw.is_available)]:
            ShootgunClawCombo.onConstraint(c)
        
        #시미터 - 체이스
        SimiterChaseCombo = core.DamageSkill('시미터 - 체이스', 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1_Cancel, SummonCuttingSimiter, ChainArts_Chais]:
            SimiterChaseCombo.onAfter(i)
            
        for c in [core.ConstraintElement('시미터', SummonCuttingSimiter, SummonCuttingSimiter.is_available)]:
            SimiterChaseCombo.onConstraint(c)
            
        # 나이프
        KnifeCombo = core.DamageSkill("나이프", 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1_Cancel, SummonSlachingKnife]:
            KnifeCombo.onAfter(i)

        for c in [core.ConstraintElement('나이프', SummonSlachingKnife, SummonSlachingKnife.is_available)]:
            KnifeCombo.onConstraint(c)
            
        # 봄-브릭
        BommBrickCombo = core.DamageSkill("봄-브릭", 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1_Cancel, SummonReleasingBoom, ChainArts_Stroke_1_Cancel, SummonStrikingBrick]:
            BommBrickCombo.onAfter(i)
            
        for c in [core.ConstraintElement('봄', SummonReleasingBoom, SummonReleasingBoom.is_available),
                    core.ConstraintElement('브릭', SummonStrikingBrick, SummonStrikingBrick.is_available)]:
            BommBrickCombo.onConstraint(c)	
        
        #평타
        NormalAttack = core.DamageSkill("평타", 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1, ChainArts_Stroke_2]:
            NormalAttack.onAfter(i)
            
        #윙대거
        WingDaggerCombo = core.DamageSkill("윙대거", 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1_Cancel, SummonThrowingWingdagger]:
            WingDaggerCombo.onAfter(i)

        for c in [core.ConstraintElement('윙대거', SummonThrowingWingdagger, SummonThrowingWingdagger.is_available)]:
            WingDaggerCombo.onConstraint(c)
            
        #배트
        BatCombo = core.DamageSkill("배트", 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1_Cancel, SummonBeatingNeedlebat_1]:
            BatCombo.onAfter(i)

        for c in [core.ConstraintElement('배트', SummonBeatingNeedlebat_1, SummonBeatingNeedlebat_1.is_available)]:
           BatCombo.onConstraint(c)

        # 메일스트롬
        MaleStromCombo = core.DamageSkill("메일스트롬", 0, 0, 0).wrap(core.DamageSkillWrapper)
        for i in [ChainArts_Stroke_1, ChainArts_Stroke_2_Cancel, ChainArts_Maelstorm]:
            MaleStromCombo.onAfter(i)

        for c in [core.ConstraintElement('메일스트롬', ChainArts_Maelstorm, ChainArts_Maelstorm.check_use)]:
            MaleStromCombo.onConstraint(c)
        
        # 체인아츠 - 퓨리 연동
        # TODO: 퓨리, 프로페셔널 추가타 발동에 터프허슬/테이크다운 추가
        for s in [ChainArts_Stroke_1, ChainArts_Stroke_2, ChainArts_Stroke_1_Cancel, ChainArts_Stroke_2_Cancel,
                                SummonCuttingSimiter, SummonScratchingClaw, SummonShootingShotgun, SummonSlachingKnife, ChainArts_Chais, SummonThrowingWingdaggerEnd,
                                SummonReleasingBoom, SummonStrikingBrick, SummonBeatingNeedlebat_1, SummonBeatingNeedlebat_2, SummonBeatingNeedlebat_3]:
            s.onAfter(ChainArts_Fury_Use)
        for s in [SummonThrowingWingdaggerSummon, ChainArts_Maelstorm]:
            s.onTick(ChainArts_Fury_Use)
        
        # 프로페셔널 에이전트 추가타
        for s in [ChainArts_Stroke_1, ChainArts_Stroke_2, ChainArts_Stroke_1_Cancel, ChainArts_Stroke_2_Cancel,
                    SummonCuttingSimiter, SummonScratchingClaw, SummonShootingShotgun, SummonSlachingKnife, ChainArts_Chais, SummonThrowingWingdaggerEnd,
                    SummonReleasingBoom, SummonStrikingBrick, SummonBeatingNeedlebat_1, SummonBeatingNeedlebat_2, SummonBeatingNeedlebat_3,
                        ChainArts_Maelstorm, ChainArts_Fury_Damage]:
            s.onAfter(ProfessionalAgent_Attack)
        for s in [SummonThrowingWingdaggerSummon]:
            s.onTick(ProfessionalAgent_Attack)
        
        for s in [ChainArts_Fury_Damage, SummonShootingShotgun, SummonScratchingClaw,
                        SummonCuttingSimiter, SummonSlachingKnife,
                            SummonReleasingBoom, SummonStrikingBrick,
                                SummonBeatingNeedlebat_1, SummonThrowingWingdagger, ChainArts_Maelstorm, WeaponVarietyAttack]:
            s.protect_from_running()

        return(NormalAttack,
                [globalSkill.maple_heros(chtr.level, name = "노바의 용사", combat_level=self.combat), globalSkill.useful_sharp_eyes(), globalSkill.useful_combat_orders(),
                    WeaponVariety, Booster, SpecialPotion, ProfessionalAgent,
                    ReadyToDie, ChainArts_Fury, 
                    SummonSlachingKnife_Horror, SummonBeatingNeedlebat_Honmy, VenomBurst_Poison, ChainArts_Maelstorm_Slow,
                    globalSkill.soul_contract(), CheapShotIIBleed, CheapShotIIBleedBuff, CheapShotIIAdventureMageBuff] +\
                [AD_Odnunce_Final,
                    WingDaggerCombo, BatCombo, BommBrickCombo, ShootgunClawCombo, SimiterChaseCombo, KnifeCombo, MaleStromCombo] +\
                [WeaponVarietyAttack, SummonThrowingWingdaggerSummon, VenomBurst, AD_Odnunce, ChainArts_Maelstorm] +\
                [ChainArts_Fury_Damage, SummonThrowingWingdaggerEnd, SummonShootingShotgun, SummonScratchingClaw,
                        SummonCuttingSimiter, SummonSlachingKnife,
                            SummonReleasingBoom, SummonStrikingBrick,
                                SummonBeatingNeedlebat_1, SummonThrowingWingdagger] +\
                [NormalAttack])