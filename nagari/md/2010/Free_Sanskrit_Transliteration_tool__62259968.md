_Created: 15-08-2026 · Last updated: 05-09-2026_

---
thread_id: 11049362259968
subject: "Free Sanskrit Transliteration tool"
year: 2010
messages: 8
participants: "Worga, Serge"
first: 2010-11-21T23:41:03+03:00
last: 2010-11-26T22:57:27+03:00
source_url: https://groups.google.com/d/msgid/nagari/06d88401-a630-488b-9a0f-2d43576a0b4a@z19g2000yqb.googlegroups.com
---

# Free Sanskrit Transliteration tool

[Читать оригинальный тред в Google Groups](https://groups.google.com/d/msgid/nagari/06d88401-a630-488b-9a0f-2d43576a0b4a@z19g2000yqb.googlegroups.com)

> 8 сообщений · 2 участников · 2010-11-21 — 2010-11-26

## 1. Worga — 2010-11-21 23:41:03

Here is a free Sanskrit transliteration program - a stand alone

utility for transliteration from/to Devanāgarī using Harvard-Kyoto,

ITRANS, IAST, SLP1 and Velthui's transliteration schemes.



The screenshot is here:



http://www.kavitype.com/kavitype/images/kvttranslit.png



Download link is here:



http://www.kavitype.com/download/kvttranslit.zip



(~1.5 mb)



Please post your bug reports (if any) and improvement requests or

requests for additional functionalities here.

## 2. Serge — 2010-11-26 19:43:00

Очень удивился, обнаружив, что KaviType Transliteration сделан
несовместимым со стандартным итрансом.

например
дэванагари कृष्णः क् + ऋ + ष् + ण् + अ + ः
в итрансе k + RRi/R^i + Sh/shh + N + a + H
т.е. в итрансе возможно 4 варианта написания
kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH
программа перекодировки ни один не обрабатывает верно и выдаёт
कृSह्णः कृष्ह्णः क्R^इSह्णः क्R^इष्ह्णः
и наоборот, берём कृष्णः, и программа выдаёт kRRishNaH
что в итрансе соответствует कृश्णः, т.е. тоже неверно
а श и вовсе через ssha кодируется в этом псевдоитрансе...

По результатам первого тестирования - незачёт.

:(

Но, как оказалось, эта фигня легко исправляется в соответствующем
файле транслитерации. И тогда всё будет работать правильно. Да и
вообще свою схему можно сделать. Это хорошо.

Так что всё-таки зачёт.

:)


On Nov 21, 11:41 pm, Worga <swo...@…> wrote:
> Here is a free Sanskrit transliteration program - a stand alone
> utility for transliteration from/to Devanāgarī using Harvard-Kyoto,
> ITRANS, IAST, SLP1 and Velthui's transliteration schemes.
>
> The screenshot is here:
>
> http://www.kavitype.com/kavitype/images/kvttranslit.png
>
> Download link is here:
>
> http://www.kavitype.com/download/kvttranslit.zip
>
> (~1.5 mb)
>
> Please post your bug reports (if any) and improvement requests or
> requests for additional functionalities here.

## 3. Worga — 2010-11-26 20:44:28

Приятно слышать. С диалектами ITRANSа - да, не все варианты были
учтены. Завтра будет новая версия...

On 26 Nov., 17:43, Serge <renuv...@…> wrote:
> Очень удивился, обнаружив, что KaviType Transliteration сделан
> несовместимым со стандартным итрансом.
>
> например
> дэванагари कृष्णः क् + ऋ + ष् + ण् + अ + ः
> в итрансе k + RRi/R^i + Sh/shh + N + a + H
> т.е. в итрансе возможно 4 варианта написания
> kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH
> программа перекодировки ни один не обрабатывает верно и выдаёт
> कृSह्णः कृष्ह्णः क्R^इSह्णः क्R^इष्ह्णः
> и наоборот, берём कृष्णः, и программа выдаёт kRRishNaH
> что в итрансе соответствует कृश्णः, т.е. тоже неверно
> а श и вовсе через ssha кодируется в этом псевдоитрансе...
>
> По результатам первого тестирования - незачёт.
>
> :(
>
> Но, как оказалось, эта фигня легко исправляется в соответствующем
> файле транслитерации. И тогда всё будет работать правильно. Да и
> вообще свою схему можно сделать. Это хорошо.
>
> Так что всё-таки зачёт.
>
> :)
>
> On Nov 21, 11:41 pm, Worga <swo...@…> wrote:
>
> > Here is a free Sanskrit transliteration program - a stand alone
> > utility for transliteration from/to Devanāgarī using Harvard-Kyoto,
> > ITRANS, IAST, SLP1 and Velthui's transliteration schemes.
>
> > The screenshot is here:
>
> >http://www.kavitype.com/kavitype/images/kvttranslit.png
>
> > Download link is here:
>
> >http://www.kavitype.com/download/kvttranslit.zip
>
> > (~1.5 mb)
>
> > Please post your bug reports (if any) and improvement requests or
> > requests for additional functionalities here.

## 4. Serge — 2010-11-26 21:27:53

Для справки по итранс.
http://www.aczoom.com/itrans/html/dvng/node3.html

Повозившись, так и не сумел добиться правильной работы при назначении
श sha и ष shha (взаимно глючат), но нормально работает, когда стоит ष
Sha, однако многие тексты кодированы именно через shha. В общем, для
начала нужна полноценная поддержка всех вариантов итранса. Возможно,
для этого придётся подправить алгоритм. (Хотя с другой стороны, для
итранса есть итранслятор. Но итранслятор не поддерживает другие
кодировки кроме итранса.) А вообще идеально было бы иметь
универсальный конвертер, где имелся бы простой механизм создания
шаблонов для разных транслитерационных кодировок и языков, и можно
было бы конвертировать что угодно куда угодно. К примеру, из
дэванагари в кириллицу или из телугу в тибетский. :)



On Nov 26, 8:44 pm, Worga <swo...@…> wrote:
> Приятно слышать. С диалектами ITRANSа - да, не все варианты были
> учтены. Завтра будет новая версия...
>
> On 26 Nov., 17:43, Serge <renuv...@…> wrote:
>
> > Очень удивился, обнаружив, что KaviType Transliteration сделан
> > несовместимым со стандартным итрансом.
>
> > например
> > дэванагари कृष्णः क् + ऋ + ष् + ण् + अ + ः
> > в итрансе k + RRi/R^i + Sh/shh + N + a + H
> > т.е. в итрансе возможно 4 варианта написания
> > kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH
> > программа перекодировки ни один не обрабатывает верно и выдаёт
> > कृSह्णः कृष्ह्णः क्R^इSह्णः क्R^इष्ह्णः
> > и наоборот, берём कृष्णः, и программа выдаёт kRRishNaH
> > что в итрансе соответствует कृश्णः, т.е. тоже неверно
> > а श и вовсе через ssha кодируется в этом псевдоитрансе...
>
> > По результатам первого тестирования - незачёт.
>
> > :(
>
> > Но, как оказалось, эта фигня легко исправляется в соответствующем
> > файле транслитерации. И тогда всё будет работать правильно. Да и
> > вообще свою схему можно сделать. Это хорошо.
>
> > Так что всё-таки зачёт.
>
> > :)
>
> > On Nov 21, 11:41 pm, Worga <swo...@…> wrote:
>
> > > Here is a free Sanskrit transliteration program - a stand alone
> > > utility for transliteration from/to Devanāgarī using Harvard-Kyoto,
> > > ITRANS, IAST, SLP1 and Velthui's transliteration schemes.
>
> > > The screenshot is here:
>
> > >http://www.kavitype.com/kavitype/images/kvttranslit.png
>
> > > Download link is here:
>
> > >http://www.kavitype.com/download/kvttranslit.zip
>
> > > (~1.5 mb)
>
> > > Please post your bug reports (if any) and improvement requests or
> > > requests for additional functionalities here.

## 5. Worga — 2010-11-26 21:37:08

Можно попросить Твой файл itrans.ini и пример, где глючит, на
sworga@…
?

On 26 Nov., 19:27, Serge <renuv...@…> wrote:
> Для справки по итранс.http://www.aczoom.com/itrans/html/dvng/node3.html
>
> Повозившись, так и не сумел добиться правильной работы при назначении
> श sha и ष shha (взаимно глючат), но нормально работает, когда стоит ष
> Sha, однако многие тексты кодированы именно через shha. В общем, для
> начала нужна полноценная поддержка всех вариантов итранса. Возможно,
> для этого придётся подправить алгоритм. (Хотя с другой стороны, для
> итранса есть итранслятор. Но итранслятор не поддерживает другие
> кодировки кроме итранса.) А вообще идеально было бы иметь
> универсальный конвертер, где имелся бы простой механизм создания
> шаблонов для разных транслитерационных кодировок и языков, и можно
> было бы конвертировать что угодно куда угодно. К примеру, из
> дэванагари в кириллицу или из телугу в тибетский. :)
>
> On Nov 26, 8:44 pm, Worga <swo...@…> wrote:
>
> > Приятно слышать. С диалектами ITRANSа - да, не все варианты были
> > учтены. Завтра будет новая версия...
>
> > On 26 Nov., 17:43, Serge <renuv...@…> wrote:
>
> > > Очень удивился, обнаружив, что KaviType Transliteration сделан
> > > несовместимым со стандартным итрансом.
>
> > > например
> > > дэванагари कृष्णः क् + ऋ + ष् + ण् + अ + ः
> > > в итрансе k + RRi/R^i + Sh/shh + N + a + H
> > > т.е. в итрансе возможно 4 варианта написания
> > > kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH
> > > программа перекодировки ни один не обрабатывает верно и выдаёт
> > > कृSह्णः कृष्ह्णः क्R^इSह्णः क्R^इष्ह्णः
> > > и наоборот, берём कृष्णः, и программа выдаёт kRRishNaH
> > > что в итрансе соответствует कृश्णः, т.е. тоже неверно
> > > а श и вовсе через ssha кодируется в этом псевдоитрансе...
>
> > > По результатам первого тестирования - незачёт.
>
> > > :(
>
> > > Но, как оказалось, эта фигня легко исправляется в соответствующем
> > > файле транслитерации. И тогда всё будет работать правильно. Да и
> > > вообще свою схему можно сделать. Это хорошо.
>
> > > Так что всё-таки зачёт.
>
> > > :)
>
> > > On Nov 21, 11:41 pm, Worga <swo...@…> wrote:
>
> > > > Here is a free Sanskrit transliteration program - a stand alone
> > > > utility for transliteration from/to Devanāgarī using Harvard-Kyoto,
> > > > ITRANS, IAST, SLP1 and Velthui's transliteration schemes.
>
> > > > The screenshot is here:
>
> > > >http://www.kavitype.com/kavitype/images/kvttranslit.png
>
> > > > Download link is here:
>
> > > >http://www.kavitype.com/download/kvttranslit.zip
>
> > > > (~1.5 mb)
>
> > > > Please post your bug reports (if any) and improvement requests or
> > > > requests for additional functionalities here.

## 6. Serge — 2010-11-26 22:14:38

Ой, нет, наврал. Это я туда-сюда тыкал и в кодах чуток напутал. Не
глючит: вариант sha-shha корректно работает. Однако вот какая незадача
- попытался добавить несколько вариантов для ष, вот так:
;shh
$0937=$0073$0068$0068
;Sh
$0937=$0053$0068
;S
$0937=$0053
но вредная программа обрабатывает только тот код, который для буквы
первым указан, а остальные пропускает.


On Nov 26, 9:37 pm, Worga <swo...@…> wrote:
> Можно попросить Твой файл itrans.ini и пример, где глючит, на
> swo...@…
> ?
>
> On 26 Nov., 19:27, Serge <renuv...@…> wrote:
>
> > Для справки по итранс.http://www.aczoom.com/itrans/html/dvng/node3.html
>
> > Повозившись, так и не сумел добиться правильной работы при назначении
> > श sha и ष shha (взаимно глючат), но нормально работает, когда стоит ष
> > Sha, однако многие тексты кодированы именно через shha. В общем, для
> > начала нужна полноценная поддержка всех вариантов итранса. Возможно,
> > для этого придётся подправить алгоритм. (Хотя с другой стороны, для
> > итранса есть итранслятор. Но итранслятор не поддерживает другие
> > кодировки кроме итранса.) А вообще идеально было бы иметь
> > универсальный конвертер, где имелся бы простой механизм создания
> > шаблонов для разных транслитерационных кодировок и языков, и можно
> > было бы конвертировать что угодно куда угодно. К примеру, из
> > дэванагари в кириллицу или из телугу в тибетский. :)
>
> > On Nov 26, 8:44 pm, Worga <swo...@…> wrote:
>
> > > Приятно слышать. С диалектами ITRANSа - да, не все варианты были
> > > учтены. Завтра будет новая версия...
>
> > > On 26 Nov., 17:43, Serge <renuv...@…> wrote:
>
> > > > Очень удивился, обнаружив, что KaviType Transliteration сделан
> > > > несовместимым со стандартным итрансом.
>
> > > > например
> > > > дэванагари कृष्णः क् + ऋ + ष् + ण् + अ + ः
> > > > в итрансе k + RRi/R^i + Sh/shh + N + a + H
> > > > т.е. в итрансе возможно 4 варианта написания
> > > > kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH
> > > > программа перекодировки ни один не обрабатывает верно и выдаёт
> > > > कृSह्णः कृष्ह्णः क्R^इSह्णः क्R^इष्ह्णः
> > > > и наоборот, берём कृष्णः, и программа выдаёт kRRishNaH
> > > > что в итрансе соответствует कृश्णः, т.е. тоже неверно
> > > > а श и вовсе через ssha кодируется в этом псевдоитрансе...
>
> > > > По результатам первого тестирования - незачёт.
>
> > > > :(
>
> > > > Но, как оказалось, эта фигня легко исправляется в соответствующем
> > > > файле транслитерации. И тогда всё будет работать правильно. Да и
> > > > вообще свою схему можно сделать. Это хорошо.
>
> > > > Так что всё-таки зачёт.
>
> > > > :)
>
> > > > On Nov 21, 11:41 pm, Worga <swo...@…> wrote:
>
> > > > > Here is a free Sanskrit transliteration program - a stand alone
> > > > > utility for transliteration from/to Devanāgarī using Harvard-Kyoto,
> > > > > ITRANS, IAST, SLP1 and Velthui's transliteration schemes.
>
> > > > > The screenshot is here:
>
> > > > >http://www.kavitype.com/kavitype/images/kvttranslit.png
>
> > > > > Download link is here:
>
> > > > >http://www.kavitype.com/download/kvttranslit.zip
>
> > > > > (~1.5 mb)
>
> > > > > Please post your bug reports (if any) and improvement requests or
> > > > > requests for additional functionalities here.

## 7. Worga — 2010-11-26 22:19:02

Надо так:

;shh / Sh / S
$0937=$0073$0068$0068/$0053$0068/$0053

Все варианты для $0937 - в одну строку и разделить их между собой с
помощью slash.


On 26 Nov., 20:14, Serge <renuv...@…> wrote:
> Ой, нет, наврал. Это я туда-сюда тыкал и в кодах чуток напутал. Не
> глючит: вариант sha-shha корректно работает. Однако вот какая незадача
> - попытался добавить несколько вариантов для ष, вот так:
> ;shh
> $0937=$0073$0068$0068
> ;Sh
> $0937=$0053$0068
> ;S
> $0937=$0053
> но вредная программа обрабатывает только тот код, который для буквы
> первым указан, а остальные пропускает.
>
> On Nov 26, 9:37 pm, Worga <swo...@…> wrote:
>
> > Можно попросить Твой файл itrans.ini и пример, где глючит, на
> > swo...@…
> > ?
>
> > On 26 Nov., 19:27, Serge <renuv...@…> wrote:
>
> > > Для справки по итранс.http://www.aczoom.com/itrans/html/dvng/node3.html
>
> > > Повозившись, так и не сумел добиться правильной работы при назначении
> > > श sha и ष shha (взаимно глючат), но нормально работает, когда стоит ष
> > > Sha, однако многие тексты кодированы именно через shha. В общем, для
> > > начала нужна полноценная поддержка всех вариантов итранса. Возможно,
> > > для этого придётся подправить алгоритм. (Хотя с другой стороны, для
> > > итранса есть итранслятор. Но итранслятор не поддерживает другие
> > > кодировки кроме итранса.) А вообще идеально было бы иметь
> > > универсальный конвертер, где имелся бы простой механизм создания
> > > шаблонов для разных транслитерационных кодировок и языков, и можно
> > > было бы конвертировать что угодно куда угодно. К примеру, из
> > > дэванагари в кириллицу или из телугу в тибетский. :)
>
> > > On Nov 26, 8:44 pm, Worga <swo...@…> wrote:
>
> > > > Приятно слышать. С диалектами ITRANSа - да, не все варианты были
> > > > учтены. Завтра будет новая версия...
>
> > > > On 26 Nov., 17:43, Serge <renuv...@…> wrote:
>
> > > > > Очень удивился, обнаружив, что KaviType Transliteration сделан
> > > > > несовместимым со стандартным итрансом.
>
> > > > > например
> > > > > дэванагари कृष्णः क् + ऋ + ष् + ण् + अ + ः
> > > > > в итрансе k + RRi/R^i + Sh/shh + N + a + H
> > > > > т.е. в итрансе возможно 4 варианта написания
> > > > > kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH
> > > > > программа перекодировки ни один не обрабатывает верно и выдаёт
> > > > > कृSह्णः कृष्ह्णः क्R^इSह्णः क्R^इष्ह्णः
> > > > > и наоборот, берём कृष्णः, и программа выдаёт kRRishNaH
> > > > > что в итрансе соответствует कृश्णः, т.е. тоже неверно
> > > > > а श и вовсе через ssha кодируется в этом псевдоитрансе...
>
> > > > > По результатам первого тестирования - незачёт.
>
> > > > > :(
>
> > > > > Но, как оказалось, эта фигня легко исправляется в соответствующем
> > > > > файле транслитерации. И тогда всё будет работать правильно. Да и
> > > > > вообще свою схему можно сделать. Это хорошо.
>
> > > > > Так что всё-таки зачёт.
>
> > > > > :)
>
> > > > > On Nov 21, 11:41 pm, Worga <swo...@…> wrote:
>
> > > > > > Here is a free Sanskrit transliteration program - a stand alone
> > > > > > utility for transliteration from/to Devanāgarī using Harvard-Kyoto,
> > > > > > ITRANS, IAST, SLP1 and Velthui's transliteration schemes.
>
> > > > > > The screenshot is here:
>
> > > > > >http://www.kavitype.com/kavitype/images/kvttranslit.png
>
> > > > > > Download link is here:
>
> > > > > >http://www.kavitype.com/download/kvttranslit.zip
>
> > > > > > (~1.5 mb)
>
> > > > > > Please post your bug reports (if any) and improvement requests or
> > > > > > requests for additional functionalities here.

## 8. Worga — 2010-11-26 22:57:27

Исправлена ошибка в алгоритме. Теперь получается

kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH = कृष्णः कृष्णः कृष्णः
कृष्णः

Исправленная версия тут:

http://www.kavitype.com/download/kvttranslit.zip


On 26 Nov., 17:43, Serge <renuv...@…> wrote:
> дэванагари कृष्णः क् + ऋ + ष् + ण् + अ + ः
> в итрансе k + RRi/R^i + Sh/shh + N + a + H
> т.е. в итрансе возможно 4 варианта написания
> kRRiShNaH kRRishhNaH kR^iShNaH kR^ishhNaH

_Dr. Mārcis Gasūns_
