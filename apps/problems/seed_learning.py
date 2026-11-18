"""Seed data for practice lists and the courses catalog."""


COURSE_CATEGORIES = [
    {
        "name": "Interview Prep",
        "description": "Structured warm-ups for coding interviews.",
        "icon": "🎯",
        "order_index": 1,
    },
    {
        "name": "Algorithm Patterns",
        "description": "Reusable techniques that show up across problem sets.",
        "icon": "🧠",
        "order_index": 2,
    },
]


PRACTICE_LISTS = [
    {
        "slug": "array-string-warmup",
        "title": "Array & String Warm-up",
        "description_md": (
            "A short path through the array and string patterns that appear in "
            "almost every interview. Start here if you are rebuilding momentum."
        ),
        "order_index": 1,
        "problems": [
            "contains-duplicate",
            "best-time-to-buy-and-sell-stock",
            "valid-anagram",
            "reverse-string",
            "valid-palindrome",
            "move-zeroes",
            "longest-common-prefix",
            "fizz-buzz",
            "hamming-weight",
            "matrix-diagonal-sum",
            "maximum-subarray",
        ],
    },
    {
        "slug": "interview-core",
        "title": "Interview Core",
        "description_md": (
            "Hashing, windows, two pointers and dynamic programming in one "
            "sequence. Work through it after the warm-up, or jump to a pattern "
            "you want to revise."
        ),
        "order_index": 2,
        "problems": [
            "two-sum",
            "valid-parentheses",
            "binary-search",
            "longest-substring-without-repeating",
            "product-except-self",
            "container-with-most-water",
            "subarray-sum-equals-k",
            "coin-change",
            "number-of-islands",
            "trapping-rain-water",
            "edit-distance",
            "climbing-stairs",
        ],
    },
]


COURSES = [
    {
        "category": "Interview Prep",
        "slug": "python-interview-foundations",
        "title": "Python Interview Foundations",
        "subtitle": "Complexity, hash maps and the sliding-window habit",
        "description_md": (
            "Build the habits that make interview code predictable: estimate "
            "complexity, reach for the right data structure, then test the edge "
            "cases. Every chapter links to a problem so you can apply the idea "
            "immediately."
        ),
        "difficulty": "BEGINNER",
        "cover_icon": "🐍",
        "estimated_minutes": 90,
        "order_index": 1,
        "chapters": [
            {
                "title": "Complexity and hash maps",
                "description_md": "Estimate first, then choose a structure.",
                "order_index": 1,
                "lessons": [
                    {
                        "slug": "reading-big-o",
                        "title": "Reading Big-O quickly",
                        "content_md": (
                            "Big-O describes how work grows as input size grows. "
                            "When you read a loop, ask what it touches: a single "
                            "pass is usually `O(n)`, a nested pass over all pairs "
                            "is usually `O(n²)`.\n\n"
                            "Interviewers care about the comparison, not the exact "
                            "constant. An `O(n)` hash-map solution beats an `O(n²)` "
                            "pair scan even if the pair scan has a tiny inner loop."
                        ),
                        "problem": None,
                        "estimated_minutes": 10,
                        "order_index": 1,
                    },
                    {
                        "slug": "hash-map-two-sum",
                        "title": "Hash maps in practice",
                        "content_md": (
                            "A hash map turns a search for a value into `O(1)` "
                            "average work. For Two Sum, store each number's index "
                            "as you scan, and check for the complement before "
                            "storing the current number.\n\n"
                            "Try the linked problem with the map approach, then "
                            "explain why the brute-force pair loop is slower."
                        ),
                        "problem": "two-sum",
                        "estimated_minutes": 20,
                        "order_index": 2,
                    },
                ],
            },
            {
                "title": "Strings and sliding windows",
                "description_md": "Normalise input, then maintain a window.",
                "order_index": 2,
                "lessons": [
                    {
                        "slug": "string-normalisation",
                        "title": "Normalising strings",
                        "content_md": (
                            "Many string problems hide case and punctuation. "
                            "Write the normalisation step explicitly before the "
                            "core algorithm: lowercase, filter, or strip as the "
                            "statement requires.\n\n"
                            "A separate normalisation pass is easier to test than "
                            "scattering conditions through a loop."
                        ),
                        "problem": "valid-palindrome",
                        "estimated_minutes": 15,
                        "order_index": 1,
                    },
                    {
                        "slug": "sliding-window-template",
                        "title": "The sliding-window template",
                        "content_md": (
                            "Grow a window with the right pointer, then shrink it "
                            "with the left pointer while the window is invalid. "
                            "Keep a counter or map so each step is `O(1)`.\n\n"
                            "For the longest substring without repeats, the map "
                            "stores the last index of each character and the left "
                            "pointer jumps past a repeat."
                        ),
                        "problem": "longest-substring-without-repeating",
                        "estimated_minutes": 25,
                        "order_index": 2,
                    },
                ],
            },
        ],
    },
    {
        "category": "Algorithm Patterns",
        "slug": "patterns-that-repeat",
        "title": "Patterns That Repeat",
        "subtitle": "Two pointers and dynamic programming, applied",
        "description_md": (
            "Patterns are shortcuts for recognising a solution shape. This "
            "course pairs the two-pointer and DP patterns with worked problems, "
            "so you can describe your approach before writing code."
        ),
        "difficulty": "INTERMEDIATE",
        "cover_icon": "🧩",
        "estimated_minutes": 120,
        "order_index": 2,
        "chapters": [
            {
                "title": "Two pointers",
                "description_md": "Move one or both ends of a sequence.",
                "order_index": 1,
                "lessons": [
                    {
                        "slug": "opposite-ends",
                        "title": "Pointers from opposite ends",
                        "content_md": (
                            "When order matters but the answer depends on a pair, "
                            "start at both ends. Move the pointer that limits the "
                            "answer, and prove that you never skip the optimum.\n\n"
                            "Container With Most Water is the canonical example: "
                            "the shorter line caps the area, so moving it is safe."
                        ),
                        "problem": "container-with-most-water",
                        "estimated_minutes": 25,
                        "order_index": 1,
                    },
                    {
                        "slug": "fast-and-slow-writes",
                        "title": "Read and write pointers",
                        "content_md": (
                            "Two pointers do not have to start at opposite ends. "
                            "One pointer can read every value while another writes "
                            "the values you keep.\n\n"
                            "Use this shape for compaction problems such as moving "
                            "zeroes to the end while preserving order."
                        ),
                        "problem": "move-zeroes",
                        "estimated_minutes": 15,
                        "order_index": 2,
                    },
                ],
            },
            {
                "title": "Dynamic programming",
                "description_md": "Define the state before writing a loop.",
                "order_index": 2,
                "lessons": [
                    {
                        "slug": "dp-from-recursion",
                        "title": "From recursion to DP",
                        "content_md": (
                            "Write the recursive relation first, then notice which "
                            "subproblems repeat. Caching those results is "
                            "memoisation; filling them in order is tabulation.\n\n"
                            "Climbing stairs has a two-term recurrence, so it only "
                            "needs the previous two values."
                        ),
                        "problem": "climbing-stairs",
                        "estimated_minutes": 20,
                        "order_index": 1,
                    },
                    {
                        "slug": "coin-change-pattern",
                        "title": "Choice DP: coin change",
                        "content_md": (
                            "Define `dp[x]` as the best answer for amount `x`. At "
                            "each state, try every coin and combine the result with "
                            "the state before that coin was used.\n\n"
                            "The base case and the impossible case both matter: "
                            "`dp[0] = 0`, and unreachable amounts stay at a sentinel."
                        ),
                        "problem": "coin-change",
                        "estimated_minutes": 30,
                        "order_index": 2,
                    },
                ],
            },
        ],
    },
]
