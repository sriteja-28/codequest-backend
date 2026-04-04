"""
python manage.py seed_data

Seeds the database with:
- 3 test users (admin, pro, free)
- 5 complete problems with test cases, tags, sections, and editorial solutions
- 2 contests using those problems
- Sample ad placements and creatives
- Feature flags
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


PROBLEMS = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "number": 1,
        "difficulty": "EASY",
        "section": "HASH_MAP",
        "statement_md": """## Problem

Given an array of integers `nums` and an integer `target`, return **indices** of the two numbers such that they add up to `target`.

You may assume that each input would have **exactly one solution**, and you may not use the same element twice.

You can return the answer in any order.

## Examples

**Example 1:**
```
Input: nums = [2,7,11,15], target = 9
Output: [0,1]
Explanation: nums[0] + nums[1] == 9, we return [0, 1].
```

**Example 2:**
```
Input: nums = [3,2,4], target = 6
Output: [1,2]
```

**Example 3:**
```
Input: nums = [3,3], target = 6
Output: [0,1]
```

## Constraints
- `2 <= nums.length <= 10⁴`
- `-10⁹ <= nums[i] <= 10⁹`
- `-10⁹ <= target <= 10⁹`
- **Only one valid answer exists.**
""",
        "hints_md": "Think about what you need to find for each element.\n---\nFor each number x, you need target - x. How can you check existence in O(1)?\n---\nUse a hash map: as you iterate, store each number's index. Before storing, check if target - num already exists in the map.",
        "time_complexity_best": "O(n)",
        "time_complexity_average": "O(n)",
        "time_complexity_worst": "O(n)",
        "space_complexity": "O(n)",
        "complexity_notes_md": "Single pass through the array with O(1) hash map lookups. O(n) space for the hash map.",
        "starter_code_python":"""import sys
import json
from typing import List
 
def twoSum(nums: List[int], target: int) -> List[int]:
    # Your solution here
    pass
 
if __name__ == "__main__":
    data = sys.stdin.read().strip().splitlines()
    nums = json.loads(data[0])
    target = int(data[1])
    result = twoSum(nums, target)
    print(json.dumps(result))
""",
        "starter_code_cpp": """#include <bits/stdc++.h>
            using namespace std;

            vector<int> twoSum(vector<int>& nums, int target) {
                // Your solution here
                return {};
            }

            int main() {
                string line;
                getline(cin, line);
                
                // Parse JSON array [2,7,11,15]
                vector<int> nums;
                line = line.substr(1, line.size()-2); // Remove [ ]
                if (!line.empty()) {
                    stringstream ss(line);
                    string num;
                    while (getline(ss, num, ',')) {
                        nums.push_back(stoi(num));
                    }
                }
                
                int target;
                cin >> target;
                
                auto res = twoSum(nums, target);
                cout << "[" << res[0] << "," << res[1] << "]" << endl;
                
                return 0;
            }
            """,
        "starter_code_java": """import java.util.*;

            public class Solution {
                public int[] twoSum(int[] nums, int target) {
                    // Your solution here
                    return new int[]{};
                }

                public static void main(String[] args) {
                    Scanner sc = new Scanner(System.in);
                    
                    // Read array [2,7,11,15]
                    String line = sc.nextLine().replaceAll("[\\[\\]\\s]", "");
                    String[] parts = line.split(",");
                    int[] nums = new int[parts.length];
                    for (int i = 0; i < parts.length; i++) {
                        nums[i] = Integer.parseInt(parts[i]);
                    }
                    
                    // Read target
                    int target = Integer.parseInt(sc.nextLine().trim());
                    
                    // Get result
                    int[] res = new Solution().twoSum(nums, target);
                    System.out.println("[" + res[0] + "," + res[1] + "]");
                }
            }
            """,
        "starter_code_javascript": """const fs = require('fs');
                const lines = fs.readFileSync('/dev/stdin', 'utf8').trim().split('\\n');

                const nums = JSON.parse(lines[0]);
                const target = parseInt(lines[1]);

                /**
                * @param {number[]} nums
                * @param {number} target
                * @return {number[]}
                */
                function twoSum(nums, target) {
                    // Your solution here
                    return [];
                }

                const result = twoSum(nums, target);
                console.log(JSON.stringify(result));
                """,
        "topics": ["Array", "Hash Table"],
        "companies": ["Google", "Amazon", "Microsoft"],
        "test_cases": [
            {
                "input_data": "[2,7,11,15]\n9",
                "expected_output": "[0,1]",
                "is_sample": True,
                "explanation": "nums[0] + nums[1] = 2 + 7 = 9",
            },
            {
                "input_data": "[3,2,4]\n6",
                "expected_output": "[1,2]",
                "is_sample": True,
                "explanation": "nums[1] + nums[2] = 2 + 4 = 6",
            },
            {
                "input_data": "[3,3]\n6",
                "expected_output": "[0,1]",
                "is_sample": True,
                "explanation": "",
            },
            {
                "input_data": "[1,2,3,4,5]\n9",
                "expected_output": "[3,4]",
                "is_sample": False,
            },
            {
                "input_data": "[-1,-2,-3,-4,-5]\n-8",
                "expected_output": "[2,4]",
                "is_sample": False,
            },
        ],
        "solutions": [
            {
                "title": "Approach 1: Brute Force",
                "approach_summary_md": "Check every pair of numbers and see if they sum to target.",
                "code_python": "def twoSum(nums, target):\n    for i in range(len(nums)):\n        for j in range(i + 1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [i, j]",
                "time_complexity": "O(n²)",
                "space_complexity": "O(1)",
                "visibility": "FREE",
                "is_official": False,  # Brute force is not the official solution
            },
            {
                "title": "Approach 2: Hash Map (Optimal)",
                "approach_summary_md": """Use a hash map to store each number's index as you iterate. For each number, check if its complement (target - num) already exists in the map.

**Algorithm:**
1. Create an empty hash map `seen`
2. For each index `i` and value `num` in `nums`:
   - Compute `complement = target - num`
   - If `complement` in `seen`, return `[seen[complement], i]`
   - Otherwise, add `num → i` to `seen`
""",
                "code_python": "def twoSum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i",
                "code_cpp": "vector<int> twoSum(vector<int>& nums, int target) {\n    unordered_map<int,int> seen;\n    for (int i = 0; i < nums.size(); i++) {\n        int complement = target - nums[i];\n        if (seen.count(complement)) return {seen[complement], i};\n        seen[nums[i]] = i;\n    }\n    return {};\n}",
                "code_java": "public int[] twoSum(int[] nums, int target) {\n    Map<Integer,Integer> seen = new HashMap<>();\n    for (int i = 0; i < nums.length; i++) {\n        int complement = target - nums[i];\n        if (seen.containsKey(complement)) return new int[]{seen.get(complement), i};\n        seen.put(nums[i], i);\n    }\n    return new int[]{};\n}",
                "code_javascript": "function twoSum(nums, target) {\n    const seen = new Map();\n    for (let i = 0; i < nums.length; i++) {\n        const complement = target - nums[i];\n        if (seen.has(complement)) return [seen.get(complement), i];\n        seen.set(nums[i], i);\n    }\n}",
                "time_complexity": "O(n)",
                "space_complexity": "O(n)",
                "visibility": "FREE",
                "is_official": True,
            },
        ],
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "number": 2,
        "difficulty": "EASY",
        "section": "STACK",
        "statement_md": """## Problem

Given a string `s` containing just the characters `'('`, `')'`, `'{'`, `'}'`, `'['` and `']'`, determine if the input string is **valid**.

An input string is valid if:
1. Open brackets must be closed by the same type of brackets.
2. Open brackets must be closed in the correct order.
3. Every close bracket has a corresponding open bracket of the same type.

## Examples

**Example 1:** `s = "()"` → `true`

**Example 2:** `s = "()[]{}"` → `true`

**Example 3:** `s = "(]"` → `false`

## Constraints
- `1 <= s.length <= 10⁴`
- `s` consists of parentheses only `'()[]{}'`
""",
        "hints_md": "What data structure naturally gives you the last-opened bracket?\n---\nA stack! Push opening brackets, pop and verify when you see a closing bracket.\n---\nDon't forget to check the stack is empty at the end.",
        "time_complexity_best": "O(n)",
        "time_complexity_average": "O(n)",
        "time_complexity_worst": "O(n)",
        "space_complexity": "O(n)",
        "complexity_notes_md": "Single pass O(n), stack holds at most n/2 opening brackets → O(n) space.",
        "starter_code_python": """import sys

def isValid(s: str) -> bool:
    # Your solution here
    pass

if __name__ == "__main__":
    s = sys.stdin.read().strip()
    print("true" if isValid(s) else "false")""",
        "starter_code_cpp": """#include <bits/stdc++.h>
using namespace std;

bool isValid(string s) {
    // Your solution here
    return false;
}

int main() {
    string s;
    getline(cin, s);
    cout << (isValid(s) ? "true" : "false") << endl;
    return 0;
}""",
        "starter_code_java": """import java.util.*;

public class Solution {
    public boolean isValid(String s) {
        // Your solution here
        return false;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String s = sc.nextLine().trim();
        System.out.println(new Solution().isValid(s) ? "true" : "false");
    }
}""",
        "starter_code_javascript": """const s = require('fs').readFileSync('/dev/stdin','utf8').trim();

/**
 * @param {string} s
 * @return {boolean}
 */
function isValid(s) {
    // Your solution here
}

console.log(isValid(s) ? "true" : "false");""",
        "topics": ["String", "Stack"],
        "companies": ["Amazon", "Bloomberg", "Facebook"],
        "test_cases": [
            {
                "input_data": "()",
                "expected_output": "true",
                "is_sample": True,
                "explanation": "",
            },
            {
                "input_data": "()[]{}",
                "expected_output": "true",
                "is_sample": True,
                "explanation": "",
            },
            {
                "input_data": "(]",
                "expected_output": "false",
                "is_sample": True,
                "explanation": "",
            },
            {"input_data": "([)]", "expected_output": "false", "is_sample": False},
            {"input_data": "{[]}", "expected_output": "true", "is_sample": False},
        ],
        "solutions": [
            {
                "title": "Stack-Based Solution",
                "approach_summary_md": "Use a stack to track opening brackets. For each closing bracket, pop and verify it matches.",
                "code_python": "def isValid(s):\n    stack = []\n    mapping = {')': '(', '}': '{', ']': '['}\n    for char in s:\n        if char in mapping:\n            top = stack.pop() if stack else '#'\n            if mapping[char] != top:\n                return False\n        else:\n            stack.append(char)\n    return not stack",
                "code_cpp": "bool isValid(string s) {\n    stack<char> st;\n    for (char c : s) {\n        if (c=='(' || c=='{' || c=='[') st.push(c);\n        else {\n            if (st.empty()) return false;\n            if (c==')' && st.top()!='(') return false;\n            if (c=='}' && st.top()!='{') return false;\n            if (c==']' && st.top()!='[') return false;\n            st.pop();\n        }\n    }\n    return st.empty();\n}",
                "time_complexity": "O(n)",
                "space_complexity": "O(n)",
                "visibility": "FREE",
                "is_official": True,
            }
        ],
    },
    {
        "slug": "binary-search",
        "title": "Binary Search",
        "number": 3,
        "difficulty": "EASY",
        "section": "BINARY_SEARCH",
        "statement_md": """## Problem

Given an array of integers `nums` which is sorted in ascending order, and an integer `target`, write a function to search `target` in `nums`. If `target` exists, return its index. Otherwise, return `-1`.

You must write an algorithm with **O(log n)** runtime complexity.

## Examples

**Example 1:**
```
Input: nums = [-1,0,3,5,9,12], target = 9
Output: 4
```

**Example 2:**
```
Input: nums = [-1,0,3,5,9,12], target = 2
Output: -1
```

## Constraints
- `1 <= nums.length <= 10⁴`
- `-10⁴ < nums[i], target < 10⁴`
- All the integers in `nums` are **unique**
- `nums` is sorted in **ascending** order
""",
        "hints_md": "The array is sorted — can you eliminate half the search space each step?\n---\nCompare the middle element to target. If it's less, search right half; if greater, search left half.\n---\nUse two pointers: left=0, right=len-1. Stop when left > right.",
        "time_complexity_best": "O(1)",
        "time_complexity_average": "O(log n)",
        "time_complexity_worst": "O(log n)",
        "space_complexity": "O(1)",
        "complexity_notes_md": "Halves the search space each iteration → O(log n). Iterative approach uses O(1) space.",
        "starter_code_python": """import sys
import json
from typing import List

def search(nums: List[int], target: int) -> int:
    # Your solution here
    pass

if __name__ == "__main__":
    data = sys.stdin.read().strip().splitlines()
    nums = json.loads(data[0])
    target = int(data[1])
    print(search(nums, target))""",
        "starter_code_cpp": """#include <bits/stdc++.h>
using namespace std;

int search(vector<int>& nums, int target) {
    // Your solution here
    return -1;
}

int main() {
    string line;
    getline(cin, line);
    vector<int> nums;
    line = line.substr(1, line.size()-2);
    stringstream ss(line);
    string tok;
    while (getline(ss, tok, ',')) nums.push_back(stoi(tok));
    int target;
    cin >> target;
    cout << search(nums, target) << endl;
    return 0;
}""",
        "starter_code_java": """import java.util.*;

public class Solution {
    public int search(int[] nums, int target) {
        // Your solution here
        return -1;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String line = sc.nextLine().replaceAll("[\[\]\s]", "");
        String[] parts = line.split(",");
        int[] nums = new int[parts.length];
        for (int i = 0; i < parts.length; i++) nums[i] = Integer.parseInt(parts[i]);
        int target = Integer.parseInt(sc.nextLine().trim());
        System.out.println(new Solution().search(nums, target));
    }
}""",
        "starter_code_javascript": """const lines = require('fs').readFileSync('/dev/stdin','utf8').trim().split('\n');
const nums = JSON.parse(lines[0]);
const target = parseInt(lines[1]);

/**
 * @param {number[]} nums
 * @param {number} target
 * @return {number}
 */
function search(nums, target) {
    // Your solution here
}

console.log(search(nums, target));""",
        "topics": ["Array", "Binary Search"],
        "companies": ["Google", "Apple", "LinkedIn"],
        "test_cases": [
            {
                "input_data": "[-1,0,3,5,9,12]\n9",
                "expected_output": "4",
                "is_sample": True,
                "explanation": "9 exists at index 4",
            },
            {
                "input_data": "[-1,0,3,5,9,12]\n2",
                "expected_output": "-1",
                "is_sample": True,
                "explanation": "2 does not exist",
            },
            {"input_data": "[5]\n5", "expected_output": "0", "is_sample": False},
            {
                "input_data": "[1,2,3,4,5,6,7,8,9,10]\n7",
                "expected_output": "6",
                "is_sample": False,
            },
        ],
        "solutions": [
            {
                "title": "Iterative Binary Search",
                "approach_summary_md": "Maintain two pointers and repeatedly halve the search space.",
                "code_python": "def search(nums, target):\n    left, right = 0, len(nums) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if nums[mid] == target:\n            return mid\n        elif nums[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1",
                "code_cpp": "int search(vector<int>& nums, int target) {\n    int left = 0, right = nums.size() - 1;\n    while (left <= right) {\n        int mid = left + (right - left) / 2;\n        if (nums[mid] == target) return mid;\n        else if (nums[mid] < target) left = mid + 1;\n        else right = mid - 1;\n    }\n    return -1;\n}",
                "time_complexity": "O(log n)",
                "space_complexity": "O(1)",
                "visibility": "FREE",
                "is_official": True,
            }
        ],
    },
    {
        "slug": "longest-substring-without-repeating",
        "title": "Longest Substring Without Repeating Characters",
        "number": 4,
        "difficulty": "MEDIUM",
        "section": "SLIDING_WINDOW",
        "statement_md": """## Problem

Given a string `s`, find the length of the **longest substring** without repeating characters.

## Examples

**Example 1:**
```
Input: s = "abcabcbb"
Output: 3
Explanation: "abc" has length 3.
```

**Example 2:**
```
Input: s = "bbbbb"
Output: 1
Explanation: "b" has length 1.
```

**Example 3:**
```
Input: s = "pwwkew"
Output: 3
Explanation: "wke" has length 3.
```

## Constraints
- `0 <= s.length <= 5 * 10⁴`
- `s` consists of English letters, digits, symbols and spaces.
""",
        "hints_md": "Think about maintaining a 'window' of unique characters.\n---\nUse two pointers (left, right) expanding right and shrinking left when a repeat is found.\n---\nA hash map or set stores which characters are in the current window. When right pointer finds a duplicate, advance left until it's gone.",
        "time_complexity_best": "O(n)",
        "time_complexity_average": "O(n)",
        "time_complexity_worst": "O(n)",
        "space_complexity": "O(min(m,n))",
        "complexity_notes_md": "O(n) single pass. Space is O(min(m,n)) where m is the charset size (at most 128 for ASCII).",
        "starter_code_python": """import sys

def lengthOfLongestSubstring(s: str) -> int:
    # Your solution here
    pass

if __name__ == "__main__":
    s = sys.stdin.read().strip()
    print(lengthOfLongestSubstring(s))""",
        "starter_code_cpp": """#include <bits/stdc++.h>
using namespace std;

int lengthOfLongestSubstring(string s) {
    // Your solution here
    return 0;
}

int main() {
    string s;
    getline(cin, s);
    cout << lengthOfLongestSubstring(s) << endl;
    return 0;
}""",
        "starter_code_java": """import java.util.*;

public class Solution {
    public int lengthOfLongestSubstring(String s) {
        // Your solution here
        return 0;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String s = sc.hasNextLine() ? sc.nextLine() : "";
        System.out.println(new Solution().lengthOfLongestSubstring(s));
    }
}""",
        "starter_code_javascript": """const s = require('fs').readFileSync('/dev/stdin','utf8').trim();

/**
 * @param {string} s
 * @return {number}
 */
function lengthOfLongestSubstring(s) {
    // Your solution here
}

console.log(lengthOfLongestSubstring(s));""",
        "topics": ["Hash Table", "String", "Sliding Window"],
        "companies": ["Amazon", "Bloomberg", "Adobe"],
        "test_cases": [
            {
                "input_data": "abcabcbb",
                "expected_output": "3",
                "is_sample": True,
                "explanation": "abc",
            },
            {
                "input_data": "bbbbb",
                "expected_output": "1",
                "is_sample": True,
                "explanation": "b",
            },
            {
                "input_data": "pwwkew",
                "expected_output": "3",
                "is_sample": True,
                "explanation": "wke",
            },
            {"input_data": "", "expected_output": "0", "is_sample": False},
            {"input_data": "aab", "expected_output": "2", "is_sample": False},
        ],
        "solutions": [
            {
                "title": "Sliding Window with Hash Map",
                "approach_summary_md": "Use a sliding window with two pointers and a hash map tracking the last seen index of each character.",
                "code_python": "def lengthOfLongestSubstring(s):\n    seen = {}\n    left = 0\n    max_len = 0\n    for right, char in enumerate(s):\n        if char in seen and seen[char] >= left:\n            left = seen[char] + 1\n        seen[char] = right\n        max_len = max(max_len, right - left + 1)\n    return max_len",
                "code_cpp": "int lengthOfLongestSubstring(string s) {\n    unordered_map<char,int> seen;\n    int left = 0, maxLen = 0;\n    for (int right = 0; right < s.size(); right++) {\n        if (seen.count(s[right]) && seen[s[right]] >= left)\n            left = seen[s[right]] + 1;\n        seen[s[right]] = right;\n        maxLen = max(maxLen, right - left + 1);\n    }\n    return maxLen;\n}",
                "time_complexity": "O(n)",
                "space_complexity": "O(min(m,n))",
                "visibility": "FREE",
                "is_official": True,
            }
        ],
    },
    {
        "slug": "climbing-stairs",
        "title": "Climbing Stairs",
        "number": 5,
        "difficulty": "EASY",
        "section": "DP",
        "statement_md": """## Problem

You are climbing a staircase. It takes `n` steps to reach the top.

Each time you can either climb `1` or `2` steps. In how many **distinct ways** can you climb to the top?

## Examples

**Example 1:**
```
Input: n = 2
Output: 2
Explanation: 1+1, 2
```

**Example 2:**
```
Input: n = 3
Output: 3
Explanation: 1+1+1, 1+2, 2+1
```

## Constraints
- `1 <= n <= 45`
""",
        "hints_md": "How many ways can you reach step n?\n---\nYou arrive at step n either from step n-1 (1 step) or step n-2 (2 steps). So ways(n) = ways(n-1) + ways(n-2).\n---\nThis is the Fibonacci sequence! You only need the last two values, so O(1) space is achievable.",
        "time_complexity_best": "O(n)",
        "time_complexity_average": "O(n)",
        "time_complexity_worst": "O(n)",
        "space_complexity": "O(1)",
        "complexity_notes_md": "Linear time, constant space by only storing the previous two Fibonacci values.",
        "starter_code_python": """import sys

def climbStairs(n: int) -> int:
    # Your solution here
    pass

if __name__ == "__main__":
    n = int(sys.stdin.read().strip())
    print(climbStairs(n))""",
        "starter_code_cpp": """#include <bits/stdc++.h>
using namespace std;

int climbStairs(int n) {
    // Your solution here
    return 0;
}

int main() {
    int n;
    cin >> n;
    cout << climbStairs(n) << endl;
    return 0;
}""",
        "starter_code_java": """import java.util.*;

public class Solution {
    public int climbStairs(int n) {
        // Your solution here
        return 0;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = Integer.parseInt(sc.nextLine().trim());
        System.out.println(new Solution().climbStairs(n));
    }
}""",
        "starter_code_javascript": """const n = parseInt(require('fs').readFileSync('/dev/stdin','utf8').trim());

/**
 * @param {number} n
 * @return {number}
 */
function climbStairs(n) {
    // Your solution here
}

console.log(climbStairs(n));""",
        "topics": ["Math", "Dynamic Programming", "Memoization"],
        "companies": ["Amazon", "Apple", "Google"],
        "test_cases": [
            {
                "input_data": "2",
                "expected_output": "2",
                "is_sample": True,
                "explanation": "1+1 or 2",
            },
            {
                "input_data": "3",
                "expected_output": "3",
                "is_sample": True,
                "explanation": "1+1+1, 1+2, 2+1",
            },
            {"input_data": "1", "expected_output": "1", "is_sample": False},
            {"input_data": "10", "expected_output": "89", "is_sample": False},
            {"input_data": "45", "expected_output": "1836311903", "is_sample": False},
        ],
        "solutions": [
            {
                "title": "Dynamic Programming — O(1) Space",
                "approach_summary_md": "Recognize this as Fibonacci. Track only the previous two values.",
                "code_python": "def climbStairs(n):\n    if n <= 2:\n        return n\n    a, b = 1, 2\n    for _ in range(3, n + 1):\n        a, b = b, a + b\n    return b",
                "code_cpp": "int climbStairs(int n) {\n    if (n <= 2) return n;\n    int a = 1, b = 2;\n    for (int i = 3; i <= n; i++) {\n        int c = a + b; a = b; b = c;\n    }\n    return b;\n}",
                "time_complexity": "O(n)",
                "space_complexity": "O(1)",
                "visibility": "FREE",
                "is_official": True,
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the database with sample problems, contests, ads, and test users"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n🌱 Seeding CodeQuest database...\n")
        )
        self._create_users()
        self._create_sections()
        self._create_tags()
        self._create_problems()
        self._create_contests()
        self._create_ads()
        self._create_feature_flags()
        self.stdout.write(self.style.SUCCESS("\n✅ Seed complete!\n"))

    def _create_users(self):
        from apps.users.models import User
        from django.utils import timezone

        users_data = [
            {
                "email": "admin@codequest.dev",
                "username": "admin",
                "password": "admin123",
                "role": "ADMIN",
                "plan": "PRO",
                "display_name": "Admin",
            },
            {
                "email": "pro@codequest.dev",
                "username": "prouser",
                "password": "user123",
                "role": "USER",
                "plan": "PRO",
                "display_name": "Pro User",
                "plan_expires_at": timezone.now() + timedelta(days=365),
            },
            {
                "email": "free@codequest.dev",
                "username": "freeuser",
                "password": "user123",
                "role": "USER",
                "plan": "FREE",
                "display_name": "Free User",
            },
        ]

        for data in users_data:
            expires = data.pop("plan_expires_at", None)
            if not User.objects.filter(email=data["email"]).exists():
                user = User.objects.create_user(**data)
                if expires:
                    user.plan_expires_at = expires
                    user.save()
                self.stdout.write(f"  👤 Created user: {data['email']}")
            else:
                self.stdout.write(f"  👤 Exists: {data['email']}")

    def _create_sections(self):
        from apps.problems.models import Section

        sections = [
            ("HASH_MAP", "Hash Map / Set", "🗂️", 1),
            ("STACK", "Stack", "📚", 2),
            ("BINARY_SEARCH", "Binary Search", "🔍", 3),
            ("SLIDING_WINDOW", "Sliding Window", "🪟", 4),
            ("DP", "Dynamic Programming", "🧩", 5),
            ("ARRAY", "Array", "📊", 6),
            ("GRAPH", "Graph", "🕸️", 7),
            ("TREE", "Tree", "🌳", 8),
        ]
        for name, display, icon, order in sections:
            Section.objects.get_or_create(
                name=name,
                defaults={"display_name": display, "icon": icon, "order_index": order},
            )
        self.stdout.write(f"  📁 Sections: {len(sections)} created/verified")

    def _create_tags(self):
        from apps.problems.models import Tag

        topics = [
            "Array",
            "Hash Table",
            "String",
            "Stack",
            "Binary Search",
            "Sliding Window",
            "Dynamic Programming",
            "Math",
            "Memoization",
            "Two Pointers",
            "Linked List",
            "Tree",
            "Graph",
            "Greedy",
        ]
        companies = [
            "Google",
            "Amazon",
            "Microsoft",
            "Facebook",
            "Apple",
            "Bloomberg",
            "Adobe",
            "LinkedIn",
        ]

        for name in topics:
            Tag.objects.get_or_create(name=name, defaults={"tag_type": "TOPIC"})
        for name in companies:
            Tag.objects.get_or_create(name=name, defaults={"tag_type": "COMPANY"})
        self.stdout.write(
            f"  🏷️  Tags: {len(topics)} topics, {len(companies)} companies"
        )

    def _create_problems(self):
        from apps.problems.models import Problem, Section, Tag, TestCase, Solution

        for p_data in PROBLEMS:
            if Problem.objects.filter(slug=p_data["slug"]).exists():
                self.stdout.write(f"  📝 Exists: {p_data['slug']}")
                continue

            section = Section.objects.filter(name=p_data["section"]).first()
            problem = Problem.objects.create(
                slug=p_data["slug"],
                title=p_data["title"],
                number=p_data["number"],
                difficulty=p_data["difficulty"],
                section=section,
                statement_md=p_data["statement_md"],
                hints_md=p_data["hints_md"],
                time_complexity_best=p_data["time_complexity_best"],
                time_complexity_average=p_data["time_complexity_average"],
                time_complexity_worst=p_data["time_complexity_worst"],
                space_complexity=p_data["space_complexity"],
                complexity_notes_md=p_data["complexity_notes_md"],
                starter_code_python=p_data.get("starter_code_python", ""),
                starter_code_cpp=p_data.get("starter_code_cpp", ""),
                starter_code_java=p_data.get("starter_code_java", ""),
                starter_code_javascript=p_data.get("starter_code_javascript", ""),
                is_published=True,
            )

            # Tags
            for tag_name in p_data.get("topics", []):
                tag = Tag.objects.filter(name=tag_name, tag_type="TOPIC").first()
                if tag:
                    problem.tags.add(tag)
            for tag_name in p_data.get("companies", []):
                tag = Tag.objects.filter(name=tag_name, tag_type="COMPANY").first()
                if tag:
                    problem.tags.add(tag)

            # Test cases
            for i, tc_data in enumerate(p_data.get("test_cases", [])):
                TestCase.objects.create(
                    problem=problem,
                    input_data=tc_data["input_data"],
                    expected_output=tc_data["expected_output"],
                    is_sample=tc_data.get("is_sample", False),
                    is_hidden=not tc_data.get("is_sample", False),
                    explanation=tc_data.get("explanation", ""),
                    order_index=i,
                )

            # Solutions
            for j, sol_data in enumerate(p_data.get("solutions", [])):
                Solution.objects.create(
                    problem=problem,
                    title=sol_data["title"],
                    approach_summary_md=sol_data["approach_summary_md"],
                    code_python=sol_data.get("code_python", ""),
                    code_cpp=sol_data.get("code_cpp", ""),
                    code_java=sol_data.get("code_java", ""),
                    code_javascript=sol_data.get("code_javascript", ""),
                    time_complexity=sol_data["time_complexity"],
                    space_complexity=sol_data["space_complexity"],
                    visibility=sol_data.get("visibility", "FREE"),
                    is_official=sol_data.get("is_official", True),
                    order_index=j,
                )

            self.stdout.write(f"  📝 Created: {problem.title}")

    def _create_contests(self):
        from apps.contests.models import Contest, ContestProblem
        from apps.problems.models import Problem

        now = timezone.now()
        contests_data = [
            {
                "name": "Weekly Contest #1",
                "slug": "weekly-contest-1",
                "description_md": "A beginner-friendly weekly contest covering arrays and hash maps.",
                "start_at": now + timedelta(days=2),
                "end_at": now + timedelta(days=2, hours=2),
                "is_public": True,
                "is_rated": True,
                "problems": ["two-sum", "valid-parentheses"],
                "scores": [100, 150],
            },
            {
                "name": "Algorithm Sprint",
                "slug": "algorithm-sprint",
                "description_md": "A fast-paced sprint covering binary search, sliding window, and DP.",
                "start_at": now - timedelta(hours=1),
                "end_at": now + timedelta(hours=2),
                "is_public": True,
                "is_rated": False,
                "problems": [
                    "binary-search",
                    "longest-substring-without-repeating",
                    "climbing-stairs",
                ],
                "scores": [100, 200, 150],
            },
        ]

        for c_data in contests_data:
            contest, created = Contest.objects.get_or_create(
                slug=c_data["slug"],
                defaults={
                    "name": c_data["name"],
                    "description_md": c_data["description_md"],
                    "start_at": c_data["start_at"],
                    "end_at": c_data["end_at"],
                    "is_public": c_data["is_public"],
                    "is_rated": c_data["is_rated"],
                },
            )
            if created:
                for i, (slug, score) in enumerate(
                    zip(c_data["problems"], c_data["scores"])
                ):
                    problem = Problem.objects.filter(slug=slug).first()
                    if problem:
                        ContestProblem.objects.get_or_create(
                            contest=contest,
                            problem=problem,
                            defaults={"order_index": i, "score": score},
                        )
                self.stdout.write(f"  🏆 Created contest: {contest.name}")
            else:
                self.stdout.write(f"  🏆 Exists: {contest.name}")

    def _create_ads(self):
        from apps.content.models import AdPlacement, AdCreative

        now = timezone.now()
        placement, _ = AdPlacement.objects.get_or_create(
            key="sidebar_left",
            defaults={
                "position": "sidebar_left",
                "description": "Left sidebar ad — shown to free users only",
                "is_active": True,
                "max_per_page": 1,
            },
        )

        AdCreative.objects.get_or_create(
            name="CodeQuest Pro Upgrade Banner",
            defaults={
                "placement": placement,
                "html_snippet": """<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:20px;color:white;font-family:sans-serif;">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#64748b;margin-bottom:8px">Upgrade</div>
  <div style="font-size:18px;font-weight:700;margin-bottom:8px">Go Pro 🚀</div>
  <div style="font-size:13px;color:#94a3b8;margin-bottom:16px">Unlock AI hints, editorial solutions, and no ads.</div>
  <a href="/upgrade" style="display:block;background:#6366f1;color:white;text-align:center;padding:10px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;">Upgrade for $9/mo</a>
</div>""",
                "link_url": "/upgrade",
                "start_at": now - timedelta(days=1),
                "end_at": now + timedelta(days=365),
                "plan_target": "FREE",
                "is_active": True,
                "priority": 10,
            },
        )
        self.stdout.write("  📢 Ads created")

    def _create_feature_flags(self):
        from apps.content.models import FeatureFlag

        flags = [
            ("ai_hints_enabled", True, "Enable AI hint system"),
            ("ai_chat_enabled", True, "Enable AI problem chat"),
            ("contests_enabled", True, "Enable contests feature"),
            (
                "show_complexity_before_solve",
                False,
                "Show complexity to all users before solving",
            ),
            ("maintenance_mode", False, "Put site in read-only maintenance mode"),
        ]
        for key, value, desc in flags:
            FeatureFlag.objects.get_or_create(
                key=key, defaults={"value": value, "description": desc}
            )
        self.stdout.write(f"  🚩 Feature flags: {len(flags)} created/verified")
