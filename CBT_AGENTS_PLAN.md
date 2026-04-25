## КПТ (Когнитивно-поведенческая терапия) — фрейм

### 1. Базовая модель (core loop)

```
Ситуация → Автоматическая мысль → Эмоция → Поведение → Результат → (обратная связь)
```

---

### 2. Структура сессии (микро-фрейм)

1. Агенда
2. Актуальное состояние (check-in)
3. Разбор эпизода (1–2 кейса)
4. Работа с мыслями/убеждениями
5. Поведенческий эксперимент / план
6. Резюме
7. Домашнее задание

---

### 3. Разбор эпизода (CBT-case)

**Вход: конкретная ситуация**

| Шаг | Что фиксируется                    |
| --- | ---------------------------------- |
| S   | Ситуация (факты, контекст)         |
| AT  | Автоматические мысли               |
| E   | Эмоции (тип + интенсивность 0–100) |
| B   | Поведение                          |
| C   | Последствия                        |

---

### 4. Работа с когнициями

#### 4.1. Идентификация искажений

Типовые:

* катастрофизация
* чтение мыслей
* черно-белое мышление
* обесценивание позитивного
* персонализация

#### 4.2. Диспут (структура)

```
Мысль → Доказательства "за" → Доказательства "против" → Альтернативная мысль → Новая эмоция
```

---

### 5. Уровни глубины

| Уровень | Сущность                                     |
| ------- | -------------------------------------------- |
| L1      | Автоматические мысли                         |
| L2      | Промежуточные убеждения (правила, установки) |
| L3      | Базовые убеждения (core beliefs)             |

Связка:

```
Core belief → Rule → Automatic thought
```

---

### 6. Поведенческий блок

* Эксперименты (test hypothesis)
* Экспозиция
* Активизация (behavioral activation)

Формат:

```
Гипотеза → Действие → Наблюдение → Вывод
```

---

## Алгоритмизируемость

### Оценка

| Критерий                                  | Оценка  |
| ----------------------------------------- | ------- |
| Формализуемость                           | высокая |
| Повторяемость                             | высокая |
| Декомпозиция                              | высокая |
| Зависимость от субъективной интерпретации | средняя |
| Возможность автоматизации                 | высокая |

---

### Почему хорошо ложится на LLM

1. **Явные структуры**

   * таблицы
   * шаги
   * шаблоны

2. **Локальные трансформации текста**

   * мысль → альтернатива
   * искажение → классификация

3. **Короткие контексты**

   * один эпизод = один prompt

---

### Что легко автоматизировать

* парсинг эпизода (S/AT/E/B/C)
* классификация когнитивных искажений
* генерация альтернативных мыслей
* шаблоны диспута
* формирование домашки

---

### Что сложно

* валидация истинности убеждений
* работа с глубинными убеждениями (L3)
* перенос в реальное поведение
* устойчивое изменение паттернов

---

## Минимальный LLM-пайплайн

```
RAW текст
→ segmentation (эпизоды)
→ extract S/AT/E/B/C
→ classify distortions
→ generate alternatives
→ suggest experiment
→ log + track
```

---

## Вывод

* КПТ = структурный, процедурный фрейм
* хорошо переносится в алгоритмы
* подходит для MVP LLM-инструментов
* ограничение: глубина и реальный behavioral change

Если нужно — разложу в JSON-схему или prompt-пак.


7. Output Format (фиксированный)
[S] ситуация

[AT] мысль

[E] эмоция (0–100)

[B] поведение

[C] результат

[REVIEW]
- за:
- против:

[ALT]
альтернативная мысль

[DELTA]
эмоция: X → Y

# CBT.md

Behavioral guidelines for structured CBT-style case work. Merge with personal/project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward clarity, specificity, and iterative checking over speed or depth. For vague cases, slow down.

## 1. Clarify Before Formulating

**Don't assume. Don't mind-read. Separate facts from interpretations.**

Before analysis:
- State what is known.
- State what is inferred.
- State what is missing.
- If multiple readings exist, present them.
- If the situation is vague, ask for a concrete episode.

Ask:
- What happened?
- Where/when?
- Who was involved?
- What was the exact trigger?
- What did you think in that moment?
- What did you feel in the body/emotionally?
- What did you do next?

The test: can this be replayed as a scene?

## 2. Situation First

**One case, one episode. No life-story expansion unless needed.**

Start from a specific situation:
- not “I always fail”
- but “Yesterday at 18:00 I opened the job site and closed it after 3 minutes”

Avoid:
- global identity claims
- abstract self-diagnosis
- broad theories
- premature core-belief work

If the case is too broad, narrow it.

## 3. CBT Map

**Minimum useful structure. Nothing mystical.**

Use the basic loop:

Situation → Automatic Thought → Emotion → Body → Behavior → Consequence

Capture:
- Situation: observable facts
- Automatic thought: exact inner sentence/image
- Emotion: name + intensity 0–100
- Body: sensations/activation
- Behavior: action/avoidance/safety behavior
- Consequence: short-term relief / long-term cost

## 4. Iterative Socratic Dialogue

**Do not “correct” the thought. Test it.**

For the key automatic thought:
- What makes it feel true?
- What evidence supports it?
- What evidence does not fit?
- Is there another explanation?
- What would you say to someone else in this situation?
- What is the realistic worst / best / most likely outcome?
- What remains true even if the thought is partly correct?

Loop:
1. User answers.
2. Update formulation.
3. Check if it fits.
4. Ask next question only if useful.

Do not dump ten questions at once.

## 5. Precision Over Insight

**Better one accurate thought than five elegant interpretations.**

Work with:
- one episode
- one key automatic thought
- one main emotion
- one behavior pattern
- one small alternative response

Avoid:
- overexplaining
- symbolic interpretation
- personality typing
- deep causal stories without evidence

## 6. Belief Ladder

**Go deeper only when the surface loop is stable.**

Levels:
- Automatic thought: “They will reject me”
- Rule/assumption: “If I fail, I should not try”
- Core belief: “I am incompetent”

Move downward only if:
- the automatic thought repeats across cases
- the user confirms resonance
- the current episode cannot be explained on the surface level

Use downward arrow:
- If this were true, what would it mean?
- And if that were true, what would it say about you / others / the world?

Stop when it becomes speculative.

## 7. Behavioral Experiment

**A belief needs a test, not just a better sentence.**

Convert formulation into experiment:

Belief → Prediction → Action → Result → Learning

Example:
- Belief: “If I send a weak CV, I will be humiliated”
- Prediction: “I will get a harsh reply or be ignored”
- Action: “Send one low-stakes application”
- Result: record what happened
- Learning: update belief strength 0–100

Keep experiments:
- small
- reversible
- measurable
- low-risk

## 8. Success Criteria

**Define what counts as progress before finishing.**

Possible success criteria:
- emotion intensity drops from 80 → 60
- belief strength drops from 90 → 70
- avoidance becomes one small action
- the situation is mapped clearly
- one testable prediction is created

If nothing changes:
- the thought may be wrong
- the emotion may be mislabeled
- the case may be too abstract
- the alternative thought may be too fake
- more context is needed

## 9. Output Format

Use this when summarizing:

Situation:
Automatic thought:
Emotion:
Body:
Behavior:
Consequence:

Working hypothesis:
Evidence for:
Evidence against:
Alternative view:

Next question / experiment:
Success criterion:

