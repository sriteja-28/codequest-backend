"""Additional original seed problems for the practice catalogue.

Kept separate from seed_data.py so the original five-problem fixture stays
readable. Every statement here is original prose; only standard algorithmic
ideas are shared with other judges.
"""

import json


def _sig(name, params, return_type):
    return {
        "name": name,
        "params": [{"name": n, "type": t} for n, t in params],
        "return_type": return_type,
    }


def _tc(input_obj, output, sample=False, explanation=""):
    return {
        "input_data": json.dumps(input_obj, ensure_ascii=False),
        "expected_output": output,
        "is_sample": sample,
        "explanation": explanation,
    }


def _stmt(description, examples, constraints=()):
    parts = ["## Problem", "", description, ""]
    if examples:
        parts.extend(["## Examples", ""])
        for example in examples:
            parts.extend(["```", example, "```", ""])
    if constraints:
        parts.append("## Constraints")
        parts.append("")
        parts.extend(f"- {item}" for item in constraints)
    return "\n".join(parts).strip() + "\n"


def _problem(
    *,
    slug,
    title,
    number,
    difficulty,
    section,
    statement_md,
    signature,
    test_cases,
    topics,
    hints="",
    compare_mode="EXACT",
    complexity="O(n) time, O(n) space",
    solution="",
    solution_summary="",
    companies=(),
):
    solutions = []
    if solution:
        solutions.append({
            "title": "Reference approach",
            "approach_summary_md": solution_summary or "See the reference implementation.",
            "code_python": solution,
            "time_complexity": complexity.split(" time")[0],
            "space_complexity": complexity.split(", ")[-1],
            "visibility": "FREE",
            "is_official": True,
        })
    return {
        "slug": slug,
        "title": title,
        "number": number,
        "difficulty": difficulty,
        "section": section,
        "statement_md": statement_md,
        "hints_md": hints,
        "time_complexity_best": complexity.split(" time")[0],
        "time_complexity_average": complexity.split(" time")[0],
        "time_complexity_worst": complexity.split(" time")[0],
        "space_complexity": complexity.split(", ")[-1],
        "complexity_notes_md": solution_summary,
        "function_signature": signature,
        "compare_mode": compare_mode,
        "topics": list(topics),
        "companies": list(companies),
        "test_cases": test_cases,
        "solutions": solutions,
    }


EXTRA_PROBLEMS = [
    _problem(
        slug="reverse-string",
        title="Reverse String",
        number=6,
        difficulty="EASY",
        section="STRING",
        statement_md=_stmt(
            "Given a string `s`, return a new string containing the same characters in reverse order.",
            [
                'Input: s = "hello"\nOutput: "olleh"',
                'Input: s = "CodeQuest"\nOutput: "tseuQedoC"',
            ],
            ["1 <= s.length <= 10⁵", "s contains printable ASCII characters"],
        ),
        signature=_sig("reverseString", [("s", "string")], "string"),
        test_cases=[
            _tc({"s": "hello"}, "olleh", True, "The characters are read right to left."),
            _tc({"s": "CodeQuest"}, "tseuQedoC", True),
            _tc({"s": "a"}, "a", True),
            _tc({"s": "ab"}, "ba"),
            _tc({"s": "racecar"}, "racecar"),
        ],
        topics=["String"],
        hints="Python slicing, C++ `reverse`, or a two-pointer swap all work.\n---\nDo not print anything; return the new string.",
        complexity="O(n) time, O(n) space",
        solution="class Solution:\n    def reverseString(self, s):\n        return s[::-1]\n",
        solution_summary="Slicing builds the reversed copy in linear time.",
    ),
    _problem(
        slug="valid-palindrome",
        title="Valid Palindrome",
        number=7,
        difficulty="EASY",
        section="TWO_POINTERS",
        statement_md=_stmt(
            "A phrase is a palindrome when, after converting every uppercase letter to lowercase and removing all non-alphanumeric characters, it reads the same forwards and backwards. Given a string `s`, return `true` if it is a palindrome and `false` otherwise.",
            [
                'Input: s = "A man, a plan, a canal: Panama"\nOutput: true',
                'Input: s = "race a car"\nOutput: false',
            ],
            ["1 <= s.length <= 2 × 10⁵", "s contains printable ASCII characters"],
        ),
        signature=_sig("isPalindrome", [("s", "string")], "bool"),
        test_cases=[
            _tc({"s": "A man, a plan, a canal: Panama"}, "true", True, "Normalised: amanaplanacanalpanama"),
            _tc({"s": "race a car"}, "false", True, "Normalised: raceacar"),
            _tc({"s": " "}, "true", True, "An empty normalised string is a palindrome."),
            _tc({"s": "0P"}, "false"),
            _tc({"s": "Was it a car or a cat I saw?"}, "true"),
            _tc({"s": "ab_a"}, "true"),
        ],
        topics=["String", "Two Pointers"],
        hints="Build the filtered lowercase string first, then compare it with its reverse.\n---\nAlternatively, walk one pointer from each end and skip non-alphanumeric characters.",
        complexity="O(n) time, O(n) space",
        solution=(
            "class Solution:\n"
            "    def isPalindrome(self, s):\n"
            "        cleaned = [c.lower() for c in s if c.isalnum()]\n"
            "        return cleaned == cleaned[::-1]\n"
        ),
        solution_summary="Filter to alphanumeric characters, lowercase them, then compare with the reverse.",
    ),
    _problem(
        slug="maximum-subarray",
        title="Maximum Subarray",
        number=8,
        difficulty="EASY",
        section="ARRAY",
        statement_md=_stmt(
            "Given a non-empty integer array `nums`, return the largest sum of any contiguous subarray.",
            [
                "Input: nums = [-2,1,-3,4,-1,2,1,-5,4]\nOutput: 6",
                "Input: nums = [5,4,-1,7,8]\nOutput: 23",
            ],
            ["1 <= nums.length <= 10⁵", "-10⁴ <= nums[i] <= 10⁴"],
        ),
        signature=_sig("maxSubArray", [("nums", "int[]")], "int"),
        test_cases=[
            _tc({"nums": [-2, 1, -3, 4, -1, 2, 1, -5, 4]}, "6", True, "[4,-1,2,1] has the largest sum."),
            _tc({"nums": [1]}, "1", True),
            _tc({"nums": [5, 4, -1, 7, 8]}, "23", True, "The whole array is one subarray."),
            _tc({"nums": [-3, -1, -2]}, "-1"),
            _tc({"nums": [-2, 1]}, "1"),
            _tc({"nums": [8, -19, 5, -4, 20]}, "21"),
        ],
        topics=["Array", "Dynamic Programming"],
        hints="At each position, decide whether to extend the previous subarray or start a new one.\n---\nKeep a running sum and reset it when it becomes smaller than the current element.",
        complexity="O(n) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def maxSubArray(self, nums):\n"
            "        best = current = nums[0]\n"
            "        for value in nums[1:]:\n"
            "            current = max(value, current + value)\n"
            "            best = max(best, current)\n"
            "        return best\n"
        ),
        solution_summary="Kadane's algorithm keeps the best sum ending at the current index.",
    ),
    _problem(
        slug="contains-duplicate",
        title="Contains Duplicate",
        number=9,
        difficulty="EASY",
        section="HASH_MAP",
        statement_md=_stmt(
            "Given an integer array `nums`, return `true` if any value appears at least twice, and `false` if every value is distinct.",
            [
                "Input: nums = [1,2,3,1]\nOutput: true",
                "Input: nums = [1,2,3,4]\nOutput: false",
            ],
            ["0 <= nums.length <= 10⁵", "-10⁹ <= nums[i] <= 10⁹"],
        ),
        signature=_sig("containsDuplicate", [("nums", "int[]")], "bool"),
        test_cases=[
            _tc({"nums": [1, 2, 3, 1]}, "true", True),
            _tc({"nums": [1, 2, 3, 4]}, "false", True),
            _tc({"nums": [1, 1, 1, 3, 3, 4, 3, 2, 4, 2]}, "true", True),
            _tc({"nums": []}, "false"),
            _tc({"nums": [0, 1, 2, 3, 4, 5]}, "false"),
        ],
        topics=["Array", "Hash Table"],
        hints="A set answers 'have I seen this before?' in constant time.\n---\nReturn as soon as a repeated value is found.",
        complexity="O(n) time, O(n) space",
        solution="class Solution:\n    def containsDuplicate(self, nums):\n        return len(nums) != len(set(nums))\n",
        solution_summary="Compare the array length with the size of its set of distinct values.",
    ),
    _problem(
        slug="best-time-to-buy-and-sell-stock",
        title="Best Time to Buy and Sell Stock",
        number=10,
        difficulty="EASY",
        section="ARRAY",
        statement_md=_stmt(
            "You are given an array `prices` where `prices[i]` is the price of a stock on day `i`. You may buy on one day and sell on a later day. Return the maximum profit possible, or `0` if no profitable trade exists.",
            [
                "Input: prices = [7,1,5,3,6,4]\nOutput: 5",
                "Input: prices = [7,6,4,3,1]\nOutput: 0",
            ],
            ["1 <= prices.length <= 10⁵", "0 <= prices[i] <= 10⁴"],
        ),
        signature=_sig("maxProfit", [("prices", "int[]")], "int"),
        test_cases=[
            _tc({"prices": [7, 1, 5, 3, 6, 4]}, "5", True, "Buy at 1 and sell at 6."),
            _tc({"prices": [7, 6, 4, 3, 1]}, "0", True, "Prices only fall, so do not trade."),
            _tc({"prices": [1, 2]}, "1", True),
            _tc({"prices": [2, 4, 1]}, "2"),
            _tc({"prices": [3, 3, 3]}, "0"),
            _tc({"prices": [1, 4, 2, 7]}, "6"),
        ],
        topics=["Array", "Dynamic Programming"],
        hints="Track the cheapest price seen so far.\n---\nAt each day, the best sale today uses that minimum buy price.",
        complexity="O(n) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def maxProfit(self, prices):\n"
            "        cheapest = float('inf')\n"
            "        best = 0\n"
            "        for price in prices:\n"
            "            cheapest = min(cheapest, price)\n"
            "            best = max(best, price - cheapest)\n"
            "        return best\n"
        ),
        solution_summary="One pass tracks the minimum price and the best profit so far.",
    ),
    _problem(
        slug="valid-anagram",
        title="Valid Anagram",
        number=11,
        difficulty="EASY",
        section="HASH_MAP",
        statement_md=_stmt(
            "Given two strings `s` and `t`, return `true` when `t` is an anagram of `s`, meaning it uses exactly the same characters with the same counts. Comparison is case-sensitive.",
            [
                'Input: s = "anagram", t = "nagaram"\nOutput: true',
                'Input: s = "rat", t = "car"\nOutput: false',
            ],
            ["1 <= s.length, t.length <= 5 × 10⁴", "s and t contain lowercase English letters unless stated otherwise"],
        ),
        signature=_sig("isAnagram", [("s", "string"), ("t", "string")], "bool"),
        test_cases=[
            _tc({"s": "anagram", "t": "nagaram"}, "true", True),
            _tc({"s": "rat", "t": "car"}, "false", True),
            _tc({"s": "a", "t": "a"}, "true", True),
            _tc({"s": "a", "t": "ab"}, "false"),
            _tc({"s": "listen", "t": "silent"}, "true"),
            _tc({"s": "Abc", "t": "abc"}, "false"),
        ],
        topics=["String", "Hash Table"],
        hints="Two strings are anagrams exactly when their character counts match.\n---\nA sorted comparison also works, at the cost of extra time.",
        complexity="O(n) time, O(1) space",
        solution=(
            "from collections import Counter\n\n"
            "class Solution:\n"
            "    def isAnagram(self, s, t):\n"
            "        return Counter(s) == Counter(t)\n"
        ),
        solution_summary="Compare character frequency maps; at most 26 lowercase keys are stored.",
    ),
    _problem(
        slug="move-zeroes",
        title="Move Zeroes",
        number=12,
        difficulty="EASY",
        section="TWO_POINTERS",
        statement_md=_stmt(
            "Given an integer array `nums`, return an array with all non-zero values in their original order followed by every zero. The relative order of non-zero values must not change.",
            [
                "Input: nums = [0,1,0,3,12]\nOutput: [1,3,12,0,0]",
                "Input: nums = [0]\nOutput: [0]",
            ],
            ["1 <= nums.length <= 10⁴", "-10⁹ <= nums[i] <= 10⁹"],
        ),
        signature=_sig("moveZeroes", [("nums", "int[]")], "int[]"),
        test_cases=[
            _tc({"nums": [0, 1, 0, 3, 12]}, "[1,3,12,0,0]", True),
            _tc({"nums": [0]}, "[0]", True),
            _tc({"nums": [1]}, "[1]", True),
            _tc({"nums": [0, 0, 1]}, "[1,0,0]"),
            _tc({"nums": [4, 0, 5, 0, 0, 6]}, "[4,5,6,0,0,0]"),
        ],
        topics=["Array", "Two Pointers"],
        hints="Copy the non-zero values forward, then fill the rest with zeroes.\n---\nA write pointer records where the next kept value belongs.",
        complexity="O(n) time, O(n) space",
        solution=(
            "class Solution:\n"
            "    def moveZeroes(self, nums):\n"
            "        kept = [value for value in nums if value != 0]\n"
            "        return kept + [0] * (len(nums) - len(kept))\n"
        ),
        solution_summary="Preserve the order of non-zero values and pad with zeroes.",
    ),
    _problem(
        slug="product-except-self",
        title="Product of Array Except Self",
        number=13,
        difficulty="MEDIUM",
        section="ARRAY",
        statement_md=_stmt(
            "Given an integer array `nums`, return an array `answer` where `answer[i]` is the product of every element except `nums[i]`. Division is not allowed and the product fits in a 32-bit integer.",
            [
                "Input: nums = [1,2,3,4]\nOutput: [24,12,8,6]",
                "Input: nums = [-1,1,0,-3,3]\nOutput: [0,0,9,0,0]",
            ],
            ["2 <= nums.length <= 10⁵", "-30 <= nums[i] <= 30", "The product of any prefix or suffix fits in a 32-bit integer"],
        ),
        signature=_sig("productExceptSelf", [("nums", "int[]")], "int[]"),
        test_cases=[
            _tc({"nums": [1, 2, 3, 4]}, "[24,12,8,6]", True),
            _tc({"nums": [-1, 1, 0, -3, 3]}, "[0,0,9,0,0]", True, "Only the position that is not the zero gets a non-zero product."),
            _tc({"nums": [2, 3]}, "[3,2]", True),
            _tc({"nums": [1, 1, 1, 1]}, "[1,1,1,1]"),
            _tc({"nums": [0, 0]}, "[0,0]"),
            _tc({"nums": [5, 0, 2]}, "[0,10,0]"),
        ],
        topics=["Array"],
        hints="For each index, the answer is the product of everything to its left times everything to its right.\n---\nBuild prefix products in one pass and suffix products in another.",
        complexity="O(n) time, O(1) extra space",
        solution=(
            "class Solution:\n"
            "    def productExceptSelf(self, nums):\n"
            "        n = len(nums)\n"
            "        answer = [1] * n\n"
            "        prefix = 1\n"
            "        for i in range(n):\n"
            "            answer[i] = prefix\n"
            "            prefix *= nums[i]\n"
            "        suffix = 1\n"
            "        for i in range(n - 1, -1, -1):\n"
            "            answer[i] *= suffix\n"
            "            suffix *= nums[i]\n"
            "        return answer\n"
        ),
        solution_summary="Prefix and suffix products are combined in the output array.",
    ),
    _problem(
        slug="longest-common-prefix",
        title="Longest Common Prefix",
        number=14,
        difficulty="EASY",
        section="STRING",
        statement_md=_stmt(
            "Given an array of strings, return the longest common prefix shared by every string. Return an empty string when there is no common prefix.",
            [
                'Input: strs = ["flower","flow","flight"]\nOutput: "fl"',
                'Input: strs = ["dog","racecar","car"]\nOutput: ""',
            ],
            ["1 <= strs.length <= 200", "0 <= strs[i].length <= 200"],
        ),
        signature=_sig("longestCommonPrefix", [("strs", "string[]")], "string"),
        test_cases=[
            _tc({"strs": ["flower", "flow", "flight"]}, "fl", True),
            _tc({"strs": ["dog", "racecar", "car"]}, "", True),
            _tc({"strs": ["a"]}, "a", True),
            _tc({"strs": ["interview", "internet", "internal"]}, "inter"),
            _tc({"strs": ["same", "same", "same"]}, "same"),
            _tc({"strs": ["ab", "abc"]}, "ab"),
        ],
        topics=["String"],
        hints="Compare the first string's characters with the same position in every other string.\n---\nStop at the first mismatch or at the end of the shortest string.",
        complexity="O(n × m) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def longestCommonPrefix(self, strs):\n"
            "        if not strs:\n"
            "            return ''\n"
            "        prefix = strs[0]\n"
            "        for value in strs[1:]:\n"
            "            while not value.startswith(prefix):\n"
            "                prefix = prefix[:-1]\n"
            "                if not prefix:\n"
            "                    return ''\n"
            "        return prefix\n"
        ),
        solution_summary="Shrink the candidate prefix until every string starts with it.",
    ),
    _problem(
        slug="single-number",
        title="Single Number",
        number=15,
        difficulty="EASY",
        section="BIT_MANIPULATION",
        statement_md=_stmt(
            "Every element in `nums` appears exactly twice except for one element, which appears once. Return that single element. Use linear time and constant extra space.",
            [
                "Input: nums = [2,2,1]\nOutput: 1",
                "Input: nums = [4,1,2,1,2]\nOutput: 4",
            ],
            ["1 <= nums.length <= 3 × 10⁴", "Every element appears twice except one", "-3 × 10⁴ <= nums[i] <= 3 × 10⁴"],
        ),
        signature=_sig("singleNumber", [("nums", "int[]")], "int"),
        test_cases=[
            _tc({"nums": [2, 2, 1]}, "1", True),
            _tc({"nums": [4, 1, 2, 1, 2]}, "4", True),
            _tc({"nums": [1]}, "1", True),
            _tc({"nums": [-1, -1, -2]}, "-2"),
            _tc({"nums": [7, 3, 3]}, "7"),
        ],
        topics=["Array", "Bit Manipulation"],
        hints="XOR of a number with itself is zero.\n---\nXOR all values together; the pairs cancel out.",
        complexity="O(n) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def singleNumber(self, nums):\n"
            "        result = 0\n"
            "        for value in nums:\n"
            "            result ^= value\n"
            "        return result\n"
        ),
        solution_summary="XOR cancels every duplicated value, leaving the unique one.",
    ),
    _problem(
        slug="majority-element",
        title="Majority Element",
        number=16,
        difficulty="EASY",
        section="ARRAY",
        statement_md=_stmt(
            "Given an array `nums`, return the element that appears more than `n / 2` times. You may assume such an element always exists.",
            [
                "Input: nums = [3,2,3]\nOutput: 3",
                "Input: nums = [2,2,1,1,1,2,2]\nOutput: 2",
            ],
            ["1 <= nums.length <= 5 × 10⁴", "-10⁹ <= nums[i] <= 10⁹"],
        ),
        signature=_sig("majorityElement", [("nums", "int[]")], "int"),
        test_cases=[
            _tc({"nums": [3, 2, 3]}, "3", True),
            _tc({"nums": [2, 2, 1, 1, 1, 2, 2]}, "2", True),
            _tc({"nums": [1]}, "1", True),
            _tc({"nums": [1, 1, 2]}, "1"),
            _tc({"nums": [5, 5, 5, 2, 3]}, "5"),
        ],
        topics=["Array", "Hash Table"],
        hints="A frequency map is the straightforward solution.\n---\nBoyer-Moore voting keeps a candidate and a balance counter in one pass.",
        complexity="O(n) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def majorityElement(self, nums):\n"
            "        candidate = None\n"
            "        balance = 0\n"
            "        for value in nums:\n"
            "            if balance == 0:\n"
            "                candidate = value\n"
            "            balance += 1 if value == candidate else -1\n"
            "        return candidate\n"
        ),
        solution_summary="Boyer-Moore voting cancels different pairs and leaves the majority.",
    ),
    _problem(
        slug="fizz-buzz",
        title="Fizz Buzz",
        number=17,
        difficulty="EASY",
        section="MATH",
        statement_md=_stmt(
            "Return a list of strings from `1` to `n`. For multiples of 3 use `Fizz`, for multiples of 5 use `Buzz`, for multiples of both use `FizzBuzz`, and otherwise use the number as a string.",
            [
                'Input: n = 3\nOutput: ["1","2","Fizz"]',
                'Input: n = 5\nOutput: ["1","2","Fizz","4","Buzz"]',
            ],
            ["1 <= n <= 10⁴"],
        ),
        signature=_sig("fizzBuzz", [("n", "int")], "string[]"),
        test_cases=[
            _tc({"n": 3}, '["1","2","Fizz"]', True),
            _tc({"n": 5}, '["1","2","Fizz","4","Buzz"]', True),
            _tc({"n": 1}, '["1"]', True),
            _tc(
                {"n": 15},
                '["1","2","Fizz","4","Buzz","Fizz","7","8","Fizz","Buzz","11","Fizz","13","14","FizzBuzz"]',
            ),
            _tc({"n": 6}, '["1","2","Fizz","4","Buzz","Fizz"]'),
        ],
        topics=["Math", "String"],
        hints="Check divisibility by 15 before checking 3 or 5.\n---\nStore strings in a list rather than printing them.",
        complexity="O(n) time, O(n) space",
        solution=(
            "class Solution:\n"
            "    def fizzBuzz(self, n):\n"
            "        answer = []\n"
            "        for value in range(1, n + 1):\n"
            "            if value % 15 == 0:\n"
            "                answer.append('FizzBuzz')\n"
            "            elif value % 3 == 0:\n"
            "                answer.append('Fizz')\n"
            "            elif value % 5 == 0:\n"
            "                answer.append('Buzz')\n"
            "            else:\n"
            "                answer.append(str(value))\n"
            "        return answer\n"
        ),
        solution_summary="Build the list in order, testing 15 first.",
    ),
    _problem(
        slug="hamming-weight",
        title="Number of 1 Bits",
        number=18,
        difficulty="EASY",
        section="BIT_MANIPULATION",
        statement_md=_stmt(
            "Given a non-negative integer `n`, return the number of `1` bits in its binary representation.",
            [
                "Input: n = 11\nOutput: 3",
                "Input: n = 128\nOutput: 1",
            ],
            ["0 <= n <= 2³¹ - 1"],
        ),
        signature=_sig("hammingWeight", [("n", "int")], "int"),
        test_cases=[
            _tc({"n": 11}, "3", True, "11 is 1011 in binary."),
            _tc({"n": 128}, "1", True, "128 is 10000000 in binary."),
            _tc({"n": 0}, "0", True),
            _tc({"n": 255}, "8"),
            _tc({"n": 7}, "3"),
            _tc({"n": 1024}, "1"),
        ],
        topics=["Bit Manipulation"],
        hints="Repeatedly clear the lowest set bit with `n & (n - 1)`.\n---\nEach clearing removes exactly one 1 bit.",
        complexity="O(number of 1 bits) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def hammingWeight(self, n):\n"
            "        count = 0\n"
            "        while n:\n"
            "            n &= n - 1\n"
            "            count += 1\n"
            "        return count\n"
        ),
        solution_summary="`n & (n - 1)` clears the lowest set bit each iteration.",
    ),
    _problem(
        slug="matrix-diagonal-sum",
        title="Matrix Diagonal Sum",
        number=19,
        difficulty="EASY",
        section="MATH",
        statement_md=_stmt(
            "Given a square matrix `mat`, return the sum of its primary diagonal and secondary diagonal. Do not count the centre element twice when the side length is odd.",
            [
                "Input: mat = [[1,2,3],[4,5,6],[7,8,9]]\nOutput: 25",
                "Input: mat = [[1,2],[3,4]]\nOutput: 10",
            ],
            ["1 <= mat.length <= 100", "mat[i].length == mat.length"],
        ),
        signature=_sig("diagonalSum", [("mat", "int[][]")], "int"),
        test_cases=[
            _tc({"mat": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]}, "25", True, "1 + 5 + 9 + 3 + 7 = 25."),
            _tc({"mat": [[1, 2], [3, 4]]}, "10", True, "1 + 4 + 2 + 3 = 10."),
            _tc({"mat": [[5]]}, "5", True),
            _tc({"mat": [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]}, "8"),
            _tc({"mat": [[2, 0], [0, 2]]}, "4"),
        ],
        topics=["Matrix", "Math"],
        hints="The primary diagonal is `mat[i][i]`.\n---\nThe secondary diagonal is `mat[i][n - 1 - i]`; skip the centre when n is odd.",
        complexity="O(n) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def diagonalSum(self, mat):\n"
            "        n = len(mat)\n"
            "        total = 0\n"
            "        for i in range(n):\n"
            "            total += mat[i][i] + mat[i][n - 1 - i]\n"
            "        if n % 2:\n"
            "            total -= mat[n // 2][n // 2]\n"
            "        return total\n"
        ),
        solution_summary="Sum both diagonals and subtract the centre for odd sizes.",
    ),
    _problem(
        slug="container-with-most-water",
        title="Container With Most Water",
        number=20,
        difficulty="MEDIUM",
        section="TWO_POINTERS",
        statement_md=_stmt(
            "Given heights where each pair of lines forms a container with the x-axis, return the maximum amount of water it can hold. The container's area is the shorter line's height multiplied by the distance between the lines.",
            [
                "Input: height = [1,8,6,2,5,4,8,3,7]\nOutput: 49",
                "Input: height = [1,1]\nOutput: 1",
            ],
            ["2 <= height.length <= 10⁵", "0 <= height[i] <= 10⁴"],
        ),
        signature=_sig("maxArea", [("height", "int[]")], "int"),
        test_cases=[
            _tc({"height": [1, 8, 6, 2, 5, 4, 8, 3, 7]}, "49", True, "Use the lines at indices 1 and 8."),
            _tc({"height": [1, 1]}, "1", True),
            _tc({"height": [4, 3, 2, 1, 4]}, "16", True),
            _tc({"height": [1, 2, 1]}, "2"),
            _tc({"height": [2, 3, 4, 5, 18, 17, 6]}, "17"),
        ],
        topics=["Array", "Two Pointers"],
        hints="Start with the widest container and move the shorter line inward.\n---\nMoving the taller line cannot increase the area because the width shrinks.",
        complexity="O(n) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def maxArea(self, height):\n"
            "        left, right = 0, len(height) - 1\n"
            "        best = 0\n"
            "        while left < right:\n"
            "            best = max(best, min(height[left], height[right]) * (right - left))\n"
            "            if height[left] < height[right]:\n"
            "                left += 1\n"
            "            else:\n"
            "                right -= 1\n"
            "        return best\n"
        ),
        solution_summary="The two-pointer sweep discards the shorter line at each step.",
    ),
    _problem(
        slug="subarray-sum-equals-k",
        title="Subarray Sum Equals K",
        number=21,
        difficulty="MEDIUM",
        section="HASH_MAP",
        statement_md=_stmt(
            "Given an integer array `nums` and an integer `k`, return the number of contiguous subarrays whose sum equals `k`.",
            [
                "Input: nums = [1,1,1], k = 2\nOutput: 2",
                "Input: nums = [1,2,3], k = 3\nOutput: 2",
            ],
            ["1 <= nums.length <= 2 × 10⁴", "-1000 <= nums[i] <= 1000", "-10⁷ <= k <= 10⁷"],
        ),
        signature=_sig(
            "subarraySum",
            [("nums", "int[]"), ("k", "int")],
            "int",
        ),
        test_cases=[
            _tc({"nums": [1, 1, 1], "k": 2}, "2", True, "The two length-two subarrays."),
            _tc({"nums": [1, 2, 3], "k": 3}, "2", True, "[3] and [1,2]."),
            _tc({"nums": [1, -1, 0], "k": 0}, "3", True, "[1,-1], [0], [1,-1,0]."),
            _tc({"nums": [3, 4, 7, 2, -3, 1, 4, 2], "k": 7}, "4"),
            _tc({"nums": [1], "k": 0}, "0"),
            _tc({"nums": [0, 0, 0], "k": 0}, "6"),
        ],
        topics=["Array", "Hash Table", "Prefix Sum"],
        hints="A subarray sum is the difference of two prefix sums.\n---\nCount how many earlier prefix sums equal `current - k`.",
        complexity="O(n) time, O(n) space",
        solution=(
            "from collections import defaultdict\n\n"
            "class Solution:\n"
            "    def subarraySum(self, nums, k):\n"
            "        seen = defaultdict(int)\n"
            "        seen[0] = 1\n"
            "        prefix = 0\n"
            "        answer = 0\n"
            "        for value in nums:\n"
            "            prefix += value\n"
            "            answer += seen[prefix - k]\n"
            "            seen[prefix] += 1\n"
            "        return answer\n"
        ),
        solution_summary="A prefix-sum frequency map counts matching earlier positions.",
    ),
    _problem(
        slug="trapping-rain-water",
        title="Trapping Rain Water",
        number=22,
        difficulty="HARD",
        section="TWO_POINTERS",
        statement_md=_stmt(
            "Given an elevation map where each bar has width 1, return how many units of water are trapped after raining.",
            [
                "Input: height = [0,1,0,2,1,0,1,3,2,1,2,1]\nOutput: 6",
                "Input: height = [4,2,0,3,2,5]\nOutput: 9",
            ],
            ["1 <= height.length <= 2 × 10⁴", "0 <= height[i] <= 10⁵"],
        ),
        signature=_sig("trap", [("height", "int[]")], "int"),
        test_cases=[
            _tc({"height": [0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]}, "6", True),
            _tc({"height": [4, 2, 0, 3, 2, 5]}, "9", True),
            _tc({"height": [1, 0, 1]}, "1", True),
            _tc({"height": [5]}, "0"),
            _tc({"height": [3, 0, 2, 0, 4]}, "7"),
            _tc({"height": [2, 0, 2]}, "2"),
        ],
        topics=["Array", "Two Pointers", "Stack"],
        hints="Water above a bar is limited by the shorter of the tallest bars on each side.\n---\nWith two pointers, process the side whose maximum height is smaller.",
        complexity="O(n) time, O(1) space",
        solution=(
            "class Solution:\n"
            "    def trap(self, height):\n"
            "        left, right = 0, len(height) - 1\n"
            "        left_max = right_max = 0\n"
            "        water = 0\n"
            "        while left < right:\n"
            "            left_max = max(left_max, height[left])\n"
            "            right_max = max(right_max, height[right])\n"
            "            if left_max <= right_max:\n"
            "                water += left_max - height[left]\n"
            "                left += 1\n"
            "            else:\n"
            "                water += right_max - height[right]\n"
            "                right -= 1\n"
            "        return water\n"
        ),
        solution_summary="Two pointers track the best wall seen from each side.",
    ),
    _problem(
        slug="coin-change",
        title="Coin Change",
        number=23,
        difficulty="MEDIUM",
        section="DP",
        statement_md=_stmt(
            "You are given coin denominations and a target amount. Return the fewest coins needed to make the amount, or `-1` when it cannot be made. You have an unlimited supply of each coin.",
            [
                "Input: coins = [1,2,5], amount = 11\nOutput: 3",
                "Input: coins = [2], amount = 3\nOutput: -1",
            ],
            ["1 <= coins.length <= 12", "1 <= coins[i] <= 2³¹ - 1", "0 <= amount <= 10⁴"],
        ),
        signature=_sig(
            "coinChange",
            [("coins", "int[]"), ("amount", "int")],
            "int",
        ),
        test_cases=[
            _tc({"coins": [1, 2, 5], "amount": 11}, "3", True, "11 = 5 + 5 + 1."),
            _tc({"coins": [2], "amount": 3}, "-1", True),
            _tc({"coins": [1], "amount": 0}, "0", True),
            _tc({"coins": [1, 5, 10, 25], "amount": 30}, "2"),
            _tc({"coins": [2, 5, 10, 1], "amount": 27}, "4"),
            _tc({"coins": [3, 7], "amount": 5}, "-1"),
        ],
        topics=["Array", "Dynamic Programming"],
        hints="Let `dp[x]` be the fewest coins that make amount `x`.\n---\nTry every coin at every amount: `dp[x] = min(dp[x], dp[x - coin] + 1)`.",
        complexity="O(amount × coins) time, O(amount) space",
        solution=(
            "class Solution:\n"
            "    def coinChange(self, coins, amount):\n"
            "        dp = [amount + 1] * (amount + 1)\n"
            "        dp[0] = 0\n"
            "        for total in range(1, amount + 1):\n"
            "            for coin in coins:\n"
            "                if coin <= total:\n"
            "                    dp[total] = min(dp[total], dp[total - coin] + 1)\n"
            "        return dp[amount] if dp[amount] <= amount else -1\n"
        ),
        solution_summary="Bottom-up DP fills the minimum coin count for every amount.",
    ),
    _problem(
        slug="number-of-islands",
        title="Number of Islands",
        number=24,
        difficulty="MEDIUM",
        section="GRAPH",
        statement_md=_stmt(
            "Given a grid where `1` is land and `0` is water, return the number of islands. An island is a group of land cells connected horizontally or vertically; diagonals do not connect.",
            [
                "Input: grid = [[1,1,1,1,0],[1,1,0,1,0],[1,1,0,0,0],[0,0,0,0,0]]\nOutput: 1",
                "Input: grid = [[1,1,0,0,0],[1,1,0,0,0],[0,0,1,0,0],[0,0,0,1,1]]\nOutput: 3",
            ],
            ["1 <= grid.length, grid[0].length <= 300", "grid[i][j] is 0 or 1"],
        ),
        signature=_sig("numIslands", [("grid", "int[][]")], "int"),
        test_cases=[
            _tc(
                {"grid": [[1, 1, 1, 1, 0], [1, 1, 0, 1, 0], [1, 1, 0, 0, 0], [0, 0, 0, 0, 0]]},
                "1",
                True,
                "All land cells are connected.",
            ),
            _tc(
                {"grid": [[1, 1, 0, 0, 0], [1, 1, 0, 0, 0], [0, 0, 1, 0, 0], [0, 0, 0, 1, 1]]},
                "3",
                True,
                "One island top-left, one centre, one bottom-right.",
            ),
            _tc({"grid": [[1]]}, "1", True),
            _tc({"grid": [[0]]}, "0"),
            _tc({"grid": [[1, 0, 1], [0, 1, 0], [1, 0, 1]]}, "5"),
            _tc({"grid": [[1, 1, 0], [0, 1, 0], [0, 0, 1]]}, "2"),
        ],
        topics=["Array", "Graph", "Depth-First Search"],
        hints="Every unvisited land cell starts a new island.\n---\nFlood-fill the whole island so its other cells are not counted again.",
        complexity="O(rows × cols) time, O(rows × cols) space",
        solution=(
            "class Solution:\n"
            "    def numIslands(self, grid):\n"
            "        rows, cols = len(grid), len(grid[0])\n"
            "        count = 0\n"
            "        def sink(r, c):\n"
            "            if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] != 1:\n"
            "                return\n"
            "            grid[r][c] = 0\n"
            "            sink(r + 1, c); sink(r - 1, c); sink(r, c + 1); sink(r, c - 1)\n"
            "        for r in range(rows):\n"
            "            for c in range(cols):\n"
            "                if grid[r][c] == 1:\n"
            "                    count += 1\n"
            "                    sink(r, c)\n"
            "        return count\n"
        ),
        solution_summary="Flood-fill each discovered island and count the starts.",
    ),
    _problem(
        slug="edit-distance",
        title="Edit Distance",
        number=25,
        difficulty="HARD",
        section="DP",
        statement_md=_stmt(
            "Given two strings `word1` and `word2`, return the minimum number of single-character insertions, deletions or replacements needed to turn `word1` into `word2`.",
            [
                'Input: word1 = "horse", word2 = "ros"\nOutput: 3',
                'Input: word1 = "intention", word2 = "execution"\nOutput: 5',
            ],
            ["0 <= word1.length, word2.length <= 500", "Both strings contain lowercase English letters"],
        ),
        signature=_sig(
            "minDistance",
            [("word1", "string"), ("word2", "string")],
            "int",
        ),
        test_cases=[
            _tc({"word1": "horse", "word2": "ros"}, "3", True),
            _tc({"word1": "intention", "word2": "execution"}, "5", True),
            _tc({"word1": "", "word2": "abc"}, "3", True),
            _tc({"word1": "abc", "word2": ""}, "3"),
            _tc({"word1": "same", "word2": "same"}, "0"),
            _tc({"word1": "kitten", "word2": "sitting"}, "3"),
        ],
        topics=["String", "Dynamic Programming"],
        hints="Consider the last characters of both strings.\n---\n`dp[i][j]` uses the three operations plus the cost of a replacement.",
        complexity="O(m × n) time, O(m × n) space",
        solution=(
            "class Solution:\n"
            "    def minDistance(self, word1, word2):\n"
            "        m, n = len(word1), len(word2)\n"
            "        dp = [[0] * (n + 1) for _ in range(m + 1)]\n"
            "        for i in range(m + 1):\n"
            "            dp[i][0] = i\n"
            "        for j in range(n + 1):\n"
            "            dp[0][j] = j\n"
            "        for i in range(1, m + 1):\n"
            "            for j in range(1, n + 1):\n"
            "                if word1[i - 1] == word2[j - 1]:\n"
            "                    dp[i][j] = dp[i - 1][j - 1]\n"
            "                else:\n"
            "                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])\n"
            "        return dp[m][n]\n"
        ),
        solution_summary="Classic Levenshtein DP over prefixes of both strings.",
    ),
]
