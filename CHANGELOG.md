# Changelog

Усі суттєві зміни проєкту **SIPL Language Toolkit** документуються в цьому файлі відповідно до стандарту [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-12

### Додано
- **`CORE-01`**: Формальна специфікація мови SIPL (`grammar/sipl.lark`, `grammar/SPECIFICATION.md`) за БНФ практикуму та таблицею пріоритетів М. С. Нікітченка, а також набір із 24 позитивних і негативних тестів граматики.
- **`CORE-02`**: Парсер (`sipl.parser`) та типізовані вузли AST (`sipl.ast`: `Program`, `Assign`, `Seq`, `If`, `While`, `Block`, `Skip`, `BinOp`, `CmpOp`, `NotOp`, `OrOp`, `Var`, `Num`) із точними координатами `SourceSpan` і діагностикою `SIPLSyntaxError`.
- **`CORE-03`**: Інтерпретатор композиційної семантики SIPL (`sipl.interpreter`) із моделлю іменних даних `State`, операцією накладання $\nabla$ (`overlay`), розіменуванням $x\Rightarrow$ (`deref`) та контролем ліміту кроків `max_steps`.
- **`CORE-04`**: Подієва модель виконання та трасування `trace` (`BeforeStatement`, `AfterStatement`, `VariableChanged`, `ConditionEvaluated`, `ExecutionFinished`) із прив'язкою до формул програмної алгебри `AF_AS`, `AF_SEQ`, `AF_IF`, `AF_WH`, `AF_ID`.
- **`CORE-05`**: Консольний інтерфейс `sipl` (`parse`, `check`, `run`, `trace`, `term`, `visualize`) зі структурованим JSON-режимом (`--json`) та стабільними кодами завершення.
- **`VIS-01`**: Генератор дерева синтаксичного виводу (`sipl.visualization`) з нумерацією листків зліва направо та експортом у формати `Text`, `JSON`, `DOT` і `SVG`.
- **`SEM-01`**: Побудовник семантичних термів (`sipl.semantics`) у нотації курсу та $\LaTeX$ із покроковим протоколом застосування правил `NS_Prog`, `NS_Stm_*`, `NS_A_*`, `NS_B_*`.
- **`REL-01` / `REL-02`**: Конфігурація GitHub Actions CI, приклади програм у `examples/` та документація релізу.