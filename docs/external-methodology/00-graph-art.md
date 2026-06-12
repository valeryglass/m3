Да, тут полезно развести уровни формально.

Уровень 0. Атом

Одна сущность.

trigger: social
emotion: shame
behavior: avoid


---

Уровень 1. Pair

Связь двух сущностей.

social -> shame
shame -> avoid
evaluation -> approach

Формально:

(A,B)

или

A -> B


---

Уровень 2. Signature

Связь нескольких сущностей.

Например:

social
→ shame
→ avoid

или

thought
→ evaluation
→ shame
→ avoid

Формально:

(A,B,C)

или

(A,B,C,D)


---

Мне кажется у тебя сейчас уже фактически есть сигнатуры.

Например:

thought -> neutral_mixed -> avoid

из L1.

Это уже не pair.

Это signature.


---

Уровень 3. Episode Path

Полный путь внутри эпизода.

Например:

trigger
↓
cognition
↓
emotion
↓
behavior
↓
stc
↓
ltc


---

social
↓
evaluation
↓
shame
↓
avoid
↓
relief
↓
distance


---

Это уже почти графовый маршрут.


---

Уровень 4. Motif

Очень интересная штука.

Повторяющийся кусок графа.

Например:

evaluation
↓
avoid

встречается 30 раз.


---

или

external
↓
shame
↓
avoid

встречается 10 раз.


---

В графовой литературе это обычно называют:

motif


---

Уровень 5. Attractor

Повторяющаяся область графа.

Например:

social
evaluation
shame
avoid

постоянно ходят рядом.


---

Это уже не путь.

А регион.


---

Про гиперграф

Вот тут становится интересно.


---

Обычный граф:

social → shame
social → avoid

не знает:

> произошли ли они вместе?




---

Гиперребро знает.

{social, shame, avoid}

это одно наблюдение.


---

Для CBT это очень естественно.

Потому что эпизод часто является:

trigger
emotion
behavior

одновременно.

А не набором отдельных пар.


---

То есть вместо:

social -> shame
shame -> avoid
social -> avoid

можно хранить:

episode_17:
{
  social,
  shame,
  avoid
}


---

Симплициальный комплекс

Это уже ещё дальше.

Он позволяет сказать:

social
shame
avoid

существуют как тройка.


---

И автоматически содержит:

social-shame
social-avoid
shame-avoid

как подмножества.


---

Для твоей задачи это неожиданно может быть полезно.

Потому что эпизод естественным образом выглядит как:

simplex


---

Например:

episode:
  trigger: social
  cognition: evaluation
  emotion: shame
  behavior: avoid

становится:

{
 social,
 evaluation,
 shame,
 avoid
}


---

Но даст ли это ценность сейчас?

Честно?

Нет.

Для MVP я бы оставил:

Atom
Pair
Signature
Motif


---

То есть:

Atom
  ↓
Pair
  ↓
Signature
  ↓
Motif
  ↓
Insight


---

Гиперграфы и симплициальные комплексы я бы держал в голове как будущую математическую интерпретацию.

Потому что по сути твои эпизоды уже являются гиперрёбрами:

Episode
=
Hyperedge

Но пока у тебя 18 эпизодов, а не 18 000, они вряд ли дадут новую пользовательскую ценность.

Зато нотация вроде этой уже может быть полезна:

atom:
  emotion: shame

pair:
  shame -> avoid

signature:
  external -> shame -> avoid

motif:
  frequency(external -> shame -> avoid) = 7

attractor:
  {
    external,
    shame,
    avoid,
    evaluation
  }

Это выглядит достаточно чисто и уже хорошо ложится на твой графовый движок.
Я бы для твоего проекта зафиксировал примерно такой словарь.

L0. Первичные сущности

Это то, что приходит из одного эпизода.

Trigger

Что запустило эпизод.

trigger: social

Примеры:

social
external
thought
physical


---

Cognition

Как была обработана ситуация.

cognition: evaluation

Примеры:

evaluation
prediction
meaning


---

Emotion

Что переживалось.

emotion: shame

Примеры:

shame
joy
fear
anger
love_warmth
neutral_mixed


---

Behavior

Что было сделано.

behavior: avoid

Примеры:

approach
avoid
attack
compensate


---

Outcome

Что произошло после.

Можно делить.

short_term_outcome: relief
long_term_outcome: connection


---

L1. Структурные сущности

Получаются из нескольких атомов.

Node

Любая сущность графа.

social
shame
avoid


---

Edge

Связь двух узлов.

social → shame


---

Pair

Наблюдаемая связь двух сущностей.

social → shame

Фактически частотное ребро.


---

Transition

Переход между состояниями.

shame → avoid

Акцент на последовательность.


---

L2. Эпизодные структуры

Signature

Конкретная цепочка.

social
→ evaluation
→ shame
→ avoid

Один шаблон эпизода.


---

Episode Path

Полный маршрут эпизода.

trigger
→ cognition
→ emotion
→ behavior
→ outcome


---

Hyperedge

Эпизод как множество.

{
 social,
 evaluation,
 shame,
 avoid
}

Без порядка.


---

L3. Повторяемые структуры

Motif

Повторяющаяся сигнатура.

external
→ shame
→ avoid

встречается N раз.


---

Loop

Возвращающийся цикл.

Например:

thought
→ neutral
→ avoid
→ thought

Если появится во времени.


---

Fork

Развилка.

shame
→ avoid

shame
→ approach


---

Convergence

Схлопывание разных путей.

shame
→ avoid

fear
→ avoid


---

Bridge

Связь между двумя кластерами.

Например:

social cluster
↔
work cluster


---

L4. Области графа

Cluster

Группа связанных узлов.

social
shame
rejection
avoid


---

Attractor

Устойчивая область.

Эпизоды постоянно оказываются рядом.

social
evaluation
shame
avoid


---

Basin

Область, ведущая к аттрактору.

Например:

social
↓
evaluation
↓
shame
↓
avoid

и

external
↓
prediction
↓
shame
↓
avoid

обе попадают в один аттрактор.


---

L5. Аналитические сущности

Это уже не граф, а выводы.

Observation

Прямое наблюдение.

Evaluation встречается часто.


---

Pattern

Устойчивая закономерность.

External часто связан со стыдом.


---

Contrast

Сравнение.

Радость чаще ведёт к approach,
чем стыд.


---

Counterpattern

Исключение.

Обычно стыд ведёт к avoid,
но есть случаи approach.


---

Drift

Изменение во времени.

Social становится чаще.


---

Hypothesis

Предположение системы.

Стыд может работать как мобилизатор.


---

Insight Candidate

Кандидат на значимое наблюдение.

Вопреки ожиданиям,
стыд чаще сопровождался действием,
чем избеганием.


---

Если смотреть на твой проект как на язык, то я бы зафиксировал ядро именно так:

Atom
↓
Pair
↓
Signature
↓
Motif
↓
Attractor
↓
Pattern
↓
Insight

Это уже довольно цельная онтология для CBT-графа, отчётов и будущих LLM-пейлоадов.
Да 😄

Если продолжать тот же стиль и строить онтологию снизу вверх, то первые два уровня будут выглядеть так.


---

0. Atom

Это минимальная наблюдаемая сущность.

Например:

social

или

shame

или

avoid

Это не связь.

Не паттерн.

Не вывод.

Просто факт.


---

В твоей нотации:

trigger: social
emotion: shame
behavior: avoid


---

Каждое значение:

social
shame
avoid

является атомом.


---

Очень коротко:

atom = one observed state


---

1. Pair

Это связь двух атомов.

Например:

social → shame

или

shame → avoid


---

В отличие от атома:

social

пара уже говорит:

social связан с shame


---

Очень коротко:

pair = relation between atoms


---

В твоей системе

Atom

shame


---

Pair

social → shame


---

Signature

social → shame → avoid


---

Motif

social → shame → avoid

frequency = 12


---

Attractor

social
evaluation
shame
avoid
compensate

как устойчивая область графа.


---

Формула целиком

atom      = one state

pair      = relation between states

signature = one path

motif     = repeated path

attractor = stable region of paths


---

Очень коротко

Atom — "что есть"

Pair — "что связано"

Signature — "как это происходит"

Motif — "это повторяется"

Attractor — "сюда система часто возвращается"


Мне нравится эта лестница, потому что каждый следующий уровень собирается из предыдущего:

Atoms
  ↓
Pairs
  ↓
Signatures
  ↓
Motifs
  ↓
Attractors

И уже потом поверх них появляются:

Patterns
Contrasts
Forks
Insights

То есть инсайт — это вообще не объект графа. Это интерпретация структуры графа. Это важное разделение
Да, комбинаторика без sequence — это отдельная сущность. Я бы назвал:

Co-signature / Set Signature

Не путь:

social → shame → avoid

А набор:

{social, shame, avoid}

То есть порядок не важен, важна совместная встречаемость.
