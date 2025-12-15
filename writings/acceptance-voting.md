---
title: Acceptance Voting
layout: default
permalink: /writings/acceptance-voting
social_image: /images/acceptance-voting-ui.png
---

# Acceptance Voting

_Last updated December 15th, 2025_

<img src="/images/acceptance-voting-ui.png" style="margin:0 auto; box-shadow:0 0 5px rgba(0,0,0,0.5); width: 400px; max-width: 100%;">

## Definition

Acceptance voting is a voting method similar to [approval voting](https://en.wikipedia.org/wiki/Approval_voting) that features a distinction between acceptance and preference.

For each option, voters indicate first whether they would accept the option and second whether they prefer the option. The winning option is the one with the greatest acceptance, and if there is a tie then the winning option is the one with the greatest preference.

Mechanically speaking, acceptance voting is equivalent to two rounds of approval voting where the first round is labeled "acceptance" and the second round is labeled "preference".

## Motivation

Acceptance voting originated from the process of designing and testing the group decision-making feature in the software application that would eventually become [Harmonic](https://about.harmonic.social).

Approval voting was the original voting method used in the app, but several problems kept popping up in small groups:

* Ties were frequent in small groups, and breaking ties through random selection felt unsatisfying.
* Voters with strong preferences were often outvoted by voters without strong preferences.
* Occurrences of the [Abilene paradox](https://en.wikipedia.org/wiki/Abilene_paradox) (i.e. somehow selecting an option that nobody actually wants) were unresolvable through voting alone, even if everyone realized what was happening.

The solution to these problems that worked best came from reinterpreting the singular concept of approval as two distinct concepts: acceptance and preference. The resulting voting method worked surprisingly well, solving all of the problems listed above.

The following paragraphs explore some of the unique benefits and tradeoffs of acceptance voting.

## Voting on which options to vote on

__TL;DR, acceptance voting makes it practical to generate a list of options collaboratively.__

In order for voting to occur, there must be a list of options to vote on. But what if a group is faced with an open question and does not yet have a list of options? How does the group generate a list of options?

One common strategy to generate a list of options is to allow any member of the group to suggest whatever options they want. This works reasonably well, but because the resulting list of options is unfiltered, the list might include some options that would cause problems that are only visible to a minority of group members, potentially even just one single member.

Because acceptance voting has two categories of information, acceptance and preference, this has the effect of filtering the list of options down to a subset that is maximally acceptable and then selecting from that subset. This filtering + selection process makes it more practical to generate the list of options collaboratively rather than requiring a special authority to be designated to create a manually filtered list of options (which itself would require a group decision about who should be given that authority/responsibility).

## Instant negotiation

__TL;DR, acceptance voting achieves instant negotiation without back-and-forth communication.__

The fundamental difference between decision-making as an individual and decision-making as a group comes down to the necessity of negotiation.

As an individual making an individual decision, no negotiation is needed. You simply choose the option you most prefer. There is no need to make any distinction between preference and acceptance.

However, as an individual participating in a group decision, negotiation is necessary. You must make tradeoffs in order to find agreement between members of the group. The option that you most prefer might not be preferred by others in the group. Now the distinction between preference and acceptance becomes relevant, and acceptance is the more important factor when it comes to reaching agreement.

In group decision-making, the primary goal is usually to find an option that everyone is willing to accept, even if that option is not what you most prefer.

By prioritizing acceptance, acceptance voting enables this negotiation process to happen instantly without any back-and-forth communication between group members.

## Problems with approval voting

__TL;DR, approval voting works better for large groups than small groups.__

Approval voting works very well in scenarios where there is a large number of voters and ties are unlikely, such as in democratic elections of political representatives. But in smaller groups where ties are common, approval voting is susceptible to several problems.

One such problem is related to the so-called [tyranny of the majority](https://en.wikipedia.org/wiki/Tyranny_of_the_majority) where the group selects an option that is unacceptable to a minority of voters despite the fact that the majority would genuinely be willing to compromise if there were some means of negotiating. In these cases, acceptance voting provides a way for voters to express acceptance first so that the group can be as inclusive as possible while still factoring in preference information to select from the subset of options that are maximally acceptable.

Another problem with approval voting in small groups is the [Abilene paradox](https://en.wikipedia.org/wiki/Abilene_paradox), which occurs when the group selects an option that everyone accepts but no one actually wants. This occurs because members of the group misinterpret expressions of acceptance as expressions of preference. Acceptance voting solves this by making a clear distinction between acceptance and preference so that there's no confusion.

## Problems with acceptance voting

__TL;DR, acceptance voting works best in non-competitive contexts where group members are reasonably trustworthy.__

While acceptance voting addresses the problems with approval voting described above, it is not without tradeoffs.

For example, dishonest voters who lie about which options they would accept can gain an advantage over honest voters who express their true willingness to accept options they do not prefer. In everyday life, we encounter this kind of deception in competitive negotiation scenarios like haggling over the price of an item where the buyer or seller can bluff by claiming that their preferred price is their "final offer" when really they would be willing to accept further compromise.

For this reason, acceptance voting works best in non-competitive contexts where relative honesty can be assumed. If there is competition between group members that creates strong incentives to lie, approval voting is likely a more appropriate voting method, especially when the list of options being voted on is determined beforehand.

Another tradeoff of acceptance voting is the prioritization of acceptance over intensity of preference, which means that even very strong preferences cannot override acceptance. In most small group scenarios, this is a feature rather than a bug because it maximizes inclusivity. However, it is possible for bad actors to weaponize the inclusive nature of the decision-making process in order to dominate the group agenda.

Various factors can contribute to or mitigate these problems. Some example factors are listed below.

* whether or not votes are anonymous
* whether or not new options can be added after voting has already begun
* whether or not voters can see in-progress results and update their votes based on that information
* whether or not the final decision is determined by the results themselves or by a trusted decision-maker/moderator who interprets the results

## Group decision-making, fast and slow

[TODO]

Something something ...

* How neurons in the brain make group decisions
* Leadership hierarchies vs leaderless collectives
* Representative vs direct democracy
* "Yes, and" / improv
* Lotteries / random selection
* Sortition / generalized jury duty

(maybe this section should be a separate blog post?)

## Conclusion

[TODO]
