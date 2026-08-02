# Improvements and bugs to Change Report

1. Render "Changed Files" section as a table:

|Filename|Status|Objects changed|

2. "Detailed Changes" section
- do not wrap text in ``` text ... ``` blocks
- Output "before" contents and "after" contents in two distinct subsections as is, but "escape" the headers to avoid ruining target markdown

3 BUG: "Detailed Changes" section: output glitches for Added objects - see example below.


--- EXAMPLE BEGIN ---


#### SRS BRUD21-SRS-179

**Status:** Added

##### Text

```text
 Канал БРУД **должен** перейти в режим ручного управления тягой из режима автоматического управления тягой, если от ИВК КСУ получена команда отключения автомата тяги ("Команда включения АТ(л/п)" имеет значение "Нет").  

```

##### Attributes

| Attribute | Value                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------- |
| id        | BRUD21-SRS-179                                                                                          |
| ratio     | Переход в режим ручного управления тягой происходит по команде ИВК КСУ вследствие одной из двух причин: |
- нажатие кнопки отключения автомата тяги;
- наличие отказов БРУД, препятствующих продолжению автоматического управления тягой. |
| derive | yes |
| safety | no |
| alloc | SYS, SW, HW |
| doors-id | MC21-BRUD-SRS-1246 |
| parent |  |

#### SRS <undefined>

**Status:** Added

##### Text

```text
 Яркость надписей положений РУД **должна** изменяться в зависимости от коэффициента заполнения ШИМ входного сигнала регулировки яркости в соответствии с Таблицей 6.  

```

##### Attributes

| Attribute | Value |
|-----------|-------|
| id | <undefined> |
| links | TABLE 6 |
| parent |  |
| alloc |  |

#### SRS BRUD21-SRS-180

**Status:** Added

##### Text

```text
 Угол отклонения РУР в положении MAX REV **должен** составлять 110 ± 0,5 ° относительно угла отклонения РУР в положении IDLE.  

```

##### Attributes

| Attribute | Value |
|-----------|-------|
| id | BRUD21-SRS-180 |
| parent | КБ 8.2.6, КБ 8.2.19, ТЗ 3.3.15 |
| safety | no |
| alloc | SYS |
| doors-id | MC21-BRUD-SRS-1247 |

#### SRS BRUD21-SRS-181

--- EXAMPLE BEGIN ---