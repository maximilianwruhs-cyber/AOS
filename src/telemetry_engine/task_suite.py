"""
AOS Benchmark — Task Suite
Curated, verifiable tasks with known-correct answers.
"""
import random
import json

# ─── Math Tasks (binary correct/incorrect) ──────────────────────────────────

MATH_TASKS = [
    {"id": "math_001", "prompt": "What is 347 * 28? Reply with ONLY the number.", "answer": "9716", "type": "math"},
    {"id": "math_002", "prompt": "What is 1024 / 16? Reply with ONLY the number.", "answer": "64", "type": "math"},
    {"id": "math_003", "prompt": "What is 99 * 99? Reply with ONLY the number.", "answer": "9801", "type": "math"},
    {"id": "math_004", "prompt": "What is 2^10? Reply with ONLY the number.", "answer": "1024", "type": "math"},
    {"id": "math_005", "prompt": "What is 144 / 12? Reply with ONLY the number.", "answer": "12", "type": "math"},
    {"id": "math_006", "prompt": "What is 567 + 893? Reply with ONLY the number.", "answer": "1460", "type": "math"},
    {"id": "math_007", "prompt": "What is 15! / 14!? Reply with ONLY the number.", "answer": "15", "type": "math"},
    {"id": "math_008", "prompt": "What is the square root of 256? Reply with ONLY the number.", "answer": "16", "type": "math"},
    {"id": "math_009", "prompt": "What is 17 * 23? Reply with ONLY the number.", "answer": "391", "type": "math"},
    {"id": "math_010", "prompt": "What is 1000 - 387? Reply with ONLY the number.", "answer": "613", "type": "math"},
    {"id": "math_011", "prompt": "What is 2^15? Reply with ONLY the number.", "answer": "32768", "type": "math"},
    {"id": "math_012", "prompt": "What is 7! (7 factorial)? Reply with ONLY the number.", "answer": "5040", "type": "math"},
    {"id": "math_013", "prompt": "What is 0.125 as a fraction? Reply as a/b (e.g. 1/8).", "answer": "1/8", "type": "math"},
    {"id": "math_014", "prompt": "What is the sum of integers from 1 to 100? Reply with ONLY the number.", "answer": "5050", "type": "math"},
    {"id": "math_015", "prompt": "What is 3^5? Reply with ONLY the number.", "answer": "243", "type": "math"},
]

# ─── Code Tasks (sandbox-verifiable) ─────────────────────────────────────────

CODE_TASKS = [
    {
        "id": "code_001", "type": "code",
        "prompt": "Write a Python function `fizzbuzz(n)` that returns a list of strings from 1 to n. For multiples of 3 use 'Fizz', multiples of 5 use 'Buzz', both use 'FizzBuzz', otherwise the number as string. Reply with ONLY the Python code, no explanation.",
        "test": "result = fizzbuzz(15)\nassert result[2] == 'Fizz'\nassert result[4] == 'Buzz'\nassert result[14] == 'FizzBuzz'\nassert result[0] == '1'\nprint('PASS')",
    },
    {
        "id": "code_002", "type": "code",
        "prompt": "Write a Python function `is_palindrome(s)` that returns True if the string s is a palindrome (case-insensitive, ignoring spaces). Reply with ONLY the Python code.",
        "test": "assert is_palindrome('racecar') == True\nassert is_palindrome('hello') == False\nassert is_palindrome('A man a plan a canal Panama'.replace(' ','')) == True\nprint('PASS')",
    },
    {
        "id": "code_003", "type": "code",
        "prompt": "Write a Python function `flatten(lst)` that takes a nested list and returns a flat list. Example: flatten([1,[2,[3]],4]) -> [1,2,3,4]. Reply with ONLY the Python code.",
        "test": "assert flatten([1, [2, [3]], 4]) == [1, 2, 3, 4]\nassert flatten([]) == []\nassert flatten([[1, 2], [3, [4, 5]]]) == [1, 2, 3, 4, 5]\nprint('PASS')",
    },
    {
        "id": "code_004", "type": "code",
        "prompt": "Write a Python function `caesar_encrypt(text, shift)` that shifts each letter by `shift` positions (wrap around z->a). Keep non-letters unchanged. Reply with ONLY the Python code.",
        "test": "assert caesar_encrypt('abc', 1) == 'bcd'\nassert caesar_encrypt('xyz', 3) == 'abc'\nassert caesar_encrypt('Hello!', 0) == 'Hello!'\nprint('PASS')",
    },
    {
        "id": "code_005", "type": "code",
        "prompt": "Write a Python function `word_count(text)` that returns a dictionary mapping each word (lowercased) to its count. Reply with ONLY the Python code.",
        "test": "r = word_count('the cat sat on the mat')\nassert r['the'] == 2\nassert r['cat'] == 1\nassert r['mat'] == 1\nprint('PASS')",
    },
    {
        "id": "code_006", "type": "code",
        "prompt": "Write a Python function `binary_search(arr, target)` that returns the index of target in sorted array arr, or -1 if not found. Reply with ONLY the Python code.",
        "test": "assert binary_search([1,3,5,7,9], 5) == 2\nassert binary_search([1,3,5,7,9], 4) == -1\nassert binary_search([], 1) == -1\nassert binary_search([42], 42) == 0\nprint('PASS')",
    },
    {
        "id": "code_007", "type": "code",
        "prompt": "Write a Python function `transpose(matrix)` that returns the transpose of a 2D list. Example: transpose([[1,2],[3,4]]) -> [[1,3],[2,4]]. Reply with ONLY the Python code.",
        "test": "assert transpose([[1,2],[3,4]]) == [[1,3],[2,4]]\nassert transpose([[1,2,3]]) == [[1],[2],[3]]\nassert transpose([[1],[2],[3]]) == [[1,2,3]]\nprint('PASS')",
    },
    {
        "id": "code_008", "type": "code",
        "prompt": "Write a Python function `unique(lst)` that returns a list with duplicates removed, preserving original order. Reply with ONLY the Python code.",
        "test": "assert unique([1,2,2,3,1,4]) == [1,2,3,4]\nassert unique([]) == []\nassert unique([5,5,5]) == [5]\nprint('PASS')",
    },
    {
        "id": "code_009", "type": "code",
        "prompt": "Write a Python function `gcd(a, b)` that returns the greatest common divisor using the Euclidean algorithm. Reply with ONLY the Python code.",
        "test": "assert gcd(12, 8) == 4\nassert gcd(17, 5) == 1\nassert gcd(100, 25) == 25\nassert gcd(0, 5) == 5\nprint('PASS')",
    },
    {
        "id": "code_010", "type": "code",
        "prompt": "Write a Python function `is_balanced(s)` that checks if parentheses in string s are balanced. Only consider '(' and ')'. Reply with ONLY the Python code.",
        "test": "assert is_balanced('(())') == True\nassert is_balanced('(()') == False\nassert is_balanced('') == True\nassert is_balanced('()()()') == True\nassert is_balanced(')(') == False\nprint('PASS')",
    },
]

# ─── Factual Tasks (string-match) ────────────────────────────────────────────

FACTUAL_TASKS = [
    {"id": "fact_001", "prompt": "What is the chemical symbol for gold? Reply with ONLY the symbol.", "answer": "Au", "type": "factual"},
    {"id": "fact_002", "prompt": "In what year did the Berlin Wall fall? Reply with ONLY the year.", "answer": "1989", "type": "factual"},
    {"id": "fact_003", "prompt": "What is the speed of light in km/s (rounded to nearest thousand)? Reply with ONLY the number.", "answer": "300000", "type": "factual"},
    {"id": "fact_004", "prompt": "What planet is closest to the Sun? Reply with ONLY the name.", "answer": "Mercury", "type": "factual"},
    {"id": "fact_005", "prompt": "What is the boiling point of water in Celsius? Reply with ONLY the number.", "answer": "100", "type": "factual"},
    {"id": "fact_006", "prompt": "How many bits in a byte? Reply with ONLY the number.", "answer": "8", "type": "factual"},
    {"id": "fact_007", "prompt": "What is the atomic number of carbon? Reply with ONLY the number.", "answer": "6", "type": "factual"},
    {"id": "fact_008", "prompt": "What is the largest ocean on Earth? Reply with ONLY the name.", "answer": "Pacific", "type": "factual"},
    {"id": "fact_009", "prompt": "Who wrote 'Hamlet'? Reply with ONLY the last name.", "answer": "Shakespeare", "type": "factual"},
    {"id": "fact_010", "prompt": "What is the SI unit of electric current? Reply with ONLY the name.", "answer": "Ampere", "type": "factual"},
    {"id": "fact_011", "prompt": "What gas do plants absorb from the atmosphere? Reply with ONLY the chemical formula.", "answer": "CO2", "type": "factual"},
    {"id": "fact_012", "prompt": "What is the smallest prime number? Reply with ONLY the number.", "answer": "2", "type": "factual"},
    {"id": "fact_013", "prompt": "What year was the first moon landing? Reply with ONLY the year.", "answer": "1969", "type": "factual"},
    {"id": "fact_014", "prompt": "What is the chemical formula for table salt? Reply with ONLY the formula.", "answer": "NaCl", "type": "factual"},
    {"id": "fact_015", "prompt": "How many bones does an adult human have? Reply with ONLY the number.", "answer": "206", "type": "factual"},
]

# ─── Reasoning Tasks (LLM-as-judge) ──────────────────────────────────────────

REASONING_TASKS = [
    {
        "id": "reason_001", "type": "reasoning",
        "prompt": "Explain in 2-3 sentences why bubble sort is inefficient for large datasets.",
        "rubric": "Must mention O(n²) time complexity or quadratic behavior. Must contrast with faster alternatives or explain why nested comparisons scale poorly.",
    },
    {
        "id": "reason_002", "type": "reasoning",
        "prompt": "A farmer has 3 fields. Field A produces 2x what Field B produces. Field C produces 100kg more than Field B. Total harvest is 1100kg. How much does each field produce? Show your reasoning.",
        "rubric": "Correct answer: B=250kg, A=500kg, C=350kg. Must show algebraic setup or clear step-by-step reasoning.",
    },
    {
        "id": "reason_003", "type": "reasoning",
        "prompt": "What are the trade-offs between using a linked list vs an array for a queue implementation? Be concise.",
        "rubric": "Must mention: array has O(1) access but costly resizing/shifting; linked list has O(1) insert/delete but higher memory overhead per element. Both perspectives needed.",
    },
    {
        "id": "reason_004", "type": "reasoning",
        "prompt": "Explain the CAP theorem in distributed systems in simple terms.",
        "rubric": "Must correctly name all three: Consistency, Availability, Partition tolerance. Must state you can only guarantee two of three simultaneously.",
    },
    {
        "id": "reason_005", "type": "reasoning",
        "prompt": "Why does adding more CPU cores not always make a program faster?",
        "rubric": "Must mention Amdahl's law or the concept that serial portions limit speedup. Should mention synchronization overhead or diminishing returns.",
    },
    {
        "id": "reason_006", "type": "reasoning",
        "prompt": "Explain why a hash table has O(1) average lookup but O(n) worst case.",
        "rubric": "Must mention hash collisions causing chain/probe degradation. Should mention that good hash functions minimize collisions. Must distinguish average vs worst case.",
    },
    {
        "id": "reason_007", "type": "reasoning",
        "prompt": "A train leaves city A at 60 km/h. Another leaves city B (300km away) at 90 km/h toward A at the same time. When and where do they meet?",
        "rubric": "Correct answer: 2 hours, 120km from A (or 180km from B). Must show combined speed = 150 km/h, time = 300/150 = 2h.",
    },
    {
        "id": "reason_008", "type": "reasoning",
        "prompt": "What is the difference between concurrency and parallelism? Give a real-world analogy.",
        "rubric": "Must distinguish: concurrency = managing multiple tasks (possibly interleaved on one core); parallelism = executing multiple tasks simultaneously (multiple cores). Analogy should be apt.",
    },
    {
        "id": "reason_009", "type": "reasoning",
        "prompt": "Explain why recursion can cause a stack overflow and how to prevent it.",
        "rubric": "Must mention: each recursive call adds a stack frame; too many calls exceed stack memory. Prevention: tail recursion, iteration, or increasing stack size.",
    },
    {
        "id": "reason_010", "type": "reasoning",
        "prompt": "Why is floating-point arithmetic not always exact? Give an example.",
        "rubric": "Must mention IEEE 754 or binary representation limitations. Classic example: 0.1 + 0.2 != 0.3. Should explain that some decimals can't be represented exactly in binary.",
    },
]

# ─── Hard Math Tasks (multi-step, requires real reasoning) ────────────────────

MATH_HARD_TASKS = [
    {"id": "math_h01", "prompt": "Solve: If 3x + 2y = 16 and x - y = 1, what is x + y? Reply with ONLY the number.", "answer": "7", "type": "math"},
    {"id": "math_h02", "prompt": "What is the remainder when 2^100 is divided by 7? Reply with ONLY the number.", "answer": "2", "type": "math"},
    {"id": "math_h03", "prompt": "How many ways can you choose 3 items from 10? (10 choose 3) Reply with ONLY the number.", "answer": "120", "type": "math"},
    {"id": "math_h04", "prompt": "What is the sum of the first 20 terms of the arithmetic sequence 3, 7, 11, 15, ...? Reply with ONLY the number.", "answer": "820", "type": "math"},
    {"id": "math_h05", "prompt": "Find the GCD of 462 and 1071 using the Euclidean algorithm. Reply with ONLY the number.", "answer": "21", "type": "math"},
    {"id": "math_h06", "prompt": "What is log_2(1048576)? Reply with ONLY the number.", "answer": "20", "type": "math"},
    {"id": "math_h07", "prompt": "A ball is dropped from 100m. Each bounce reaches 60% of the previous height. What is the total distance traveled after 3 bounces (including the initial drop)? Reply with ONLY the number.", "answer": "256", "type": "math"},
    {"id": "math_h08", "prompt": "If f(x) = 2x^2 - 3x + 1, what is f(5)? Reply with ONLY the number.", "answer": "36", "type": "math"},
    {"id": "math_h09", "prompt": "Convert the binary number 11010110 to decimal. Reply with ONLY the number.", "answer": "214", "type": "math"},
    {"id": "math_h10", "prompt": "What is the 10th term of the Fibonacci sequence? (1, 1, 2, 3, 5, ...) Reply with ONLY the number.", "answer": "55", "type": "math"},
    {"id": "math_h11", "prompt": "A train travels 120km at 60km/h, then 180km at 90km/h. What is its average speed for the entire trip in km/h? Reply with ONLY the number.", "answer": "75", "type": "math"},
    {"id": "math_h12", "prompt": "How many distinct permutations of the letters in 'MISSISSIPPI' are there? Reply with ONLY the number.", "answer": "34650", "type": "math"},
    {"id": "math_h13", "prompt": "What is the determinant of the matrix [[3,1],[5,2]]? Reply with ONLY the number.", "answer": "1", "type": "math"},
    {"id": "math_h14", "prompt": "Solve: A shop gives 20% discount. After discount, 10% tax is added. Final price is €264. What was the original price in €? Reply with ONLY the number.", "answer": "300", "type": "math"},
    {"id": "math_h15", "prompt": "What is the sum of all prime numbers less than 30? Reply with ONLY the number.", "answer": "129", "type": "math"},
]

# ─── Hard Code Tasks (algorithms, data structures) ───────────────────────────

CODE_HARD_TASKS = [
    {
        "id": "code_h01", "type": "code",
        "prompt": "Write a Python function `longest_common_subseq(s1, s2)` that returns the length of the longest common subsequence of two strings using dynamic programming. Reply with ONLY the Python code.",
        "test": "assert longest_common_subseq('ABCBDAB', 'BDCAB') == 4\nassert longest_common_subseq('', 'abc') == 0\nassert longest_common_subseq('abc', 'abc') == 3\nassert longest_common_subseq('abc', 'def') == 0\nprint('PASS')",
    },
    {
        "id": "code_h02", "type": "code",
        "prompt": "Write a Python function `merge_sort(arr)` that sorts a list of integers using merge sort. Return the sorted list. Reply with ONLY the Python code.",
        "test": "assert merge_sort([38,27,43,3,9,82,10]) == [3,9,10,27,38,43,82]\nassert merge_sort([]) == []\nassert merge_sort([1]) == [1]\nassert merge_sort([5,4,3,2,1]) == [1,2,3,4,5]\nprint('PASS')",
    },
    {
        "id": "code_h03", "type": "code",
        "prompt": "Write a Python function `max_subarray_sum(arr)` that returns the maximum sum of a contiguous subarray using Kadane's algorithm. Reply with ONLY the Python code.",
        "test": "assert max_subarray_sum([-2,1,-3,4,-1,2,1,-5,4]) == 6\nassert max_subarray_sum([1]) == 1\nassert max_subarray_sum([-1,-2,-3]) == -1\nassert max_subarray_sum([5,4,-1,7,8]) == 23\nprint('PASS')",
    },
    {
        "id": "code_h04", "type": "code",
        "prompt": "Write a Python function `topological_sort(graph)` where graph is a dict mapping nodes to lists of dependencies. Return a valid ordering or empty list if cycle. Reply with ONLY the Python code.",
        "test": "r = topological_sort({'a':['b','c'],'b':['d'],'c':['d'],'d':[]})\nassert r.index('d') < r.index('b')\nassert r.index('d') < r.index('c')\nassert r.index('b') < r.index('a')\nassert topological_sort({'a':['b'],'b':['a']}) == []\nprint('PASS')",
    },
    {
        "id": "code_h05", "type": "code",
        "prompt": "Write a Python function `lru_cache_impl(capacity)` that returns a class or object with `get(key)` returning -1 on miss and `put(key, value)` evicting LRU on overflow. Reply with ONLY the Python code.",
        "test": "cache = lru_cache_impl(2)\ncache.put(1, 1)\ncache.put(2, 2)\nassert cache.get(1) == 1\ncache.put(3, 3)\nassert cache.get(2) == -1\ncache.put(4, 4)\nassert cache.get(1) == -1\nassert cache.get(3) == 3\nassert cache.get(4) == 4\nprint('PASS')",
    },
    {
        "id": "code_h06", "type": "code",
        "prompt": "Write a Python function `knapsack(weights, values, capacity)` that returns the maximum value achievable with 0/1 knapsack. Reply with ONLY the Python code.",
        "test": "assert knapsack([1,3,4,5], [1,4,5,7], 7) == 9\nassert knapsack([2,3,4,5], [3,4,5,6], 5) == 7\nassert knapsack([], [], 10) == 0\nassert knapsack([10], [100], 5) == 0\nprint('PASS')",
    },
    {
        "id": "code_h07", "type": "code",
        "prompt": "Write a Python function `eval_rpn(tokens)` that evaluates a Reverse Polish Notation expression. Tokens is a list of strings (numbers and operators +,-,*,/). Division truncates toward zero. Reply with ONLY the Python code.",
        "test": "assert eval_rpn(['2','1','+','3','*']) == 9\nassert eval_rpn(['4','13','5','/','+']) == 6\nassert eval_rpn(['10','6','9','3','+','-11','*','/','*','17','+','5','+']) == 22\nprint('PASS')",
    },
    {
        "id": "code_h08", "type": "code",
        "prompt": "Write a Python function `min_coins(coins, amount)` that returns the minimum number of coins to make the amount, or -1 if impossible. Reply with ONLY the Python code.",
        "test": "assert min_coins([1,5,10,25], 30) == 2\nassert min_coins([2], 3) == -1\nassert min_coins([1], 0) == 0\nassert min_coins([1,3,4], 6) == 2\nprint('PASS')",
    },
    {
        "id": "code_h09", "type": "code",
        "prompt": "Write a Python function `is_valid_bst(root)` where root is a dict with keys 'val', 'left', 'right' (or None). Return True if it's a valid BST. Reply with ONLY the Python code.",
        "test": "t1 = {'val':2,'left':{'val':1,'left':None,'right':None},'right':{'val':3,'left':None,'right':None}}\nassert is_valid_bst(t1) == True\nt2 = {'val':5,'left':{'val':1,'left':None,'right':None},'right':{'val':4,'left':{'val':3,'left':None,'right':None},'right':{'val':6,'left':None,'right':None}}}\nassert is_valid_bst(t2) == False\nassert is_valid_bst(None) == True\nprint('PASS')",
    },
    {
        "id": "code_h10", "type": "code",
        "prompt": "Write a Python function `longest_palindrome_substr(s)` that returns the longest palindromic substring. Reply with ONLY the Python code.",
        "test": "assert longest_palindrome_substr('babad') in ('bab','aba')\nassert longest_palindrome_substr('cbbd') == 'bb'\nassert longest_palindrome_substr('a') == 'a'\nassert longest_palindrome_substr('') == ''\nprint('PASS')",
    },
]

# ─── Hard Reasoning Tasks (ambiguous, tradeoffs, real-world) ──────────────────

REASONING_HARD_TASKS = [
    {
        "id": "reason_h01", "type": "reasoning",
        "prompt": "A self-driving car must choose: swerve left (hit 1 pedestrian), swerve right (hit a wall, injuring the passenger), or brake (50% chance of hitting 3 pedestrians). What should it do and why? Discuss the ethical frameworks involved.",
        "rubric": "Must reference at least two ethical frameworks (utilitarian, deontological, virtue ethics). Must acknowledge there's no universally correct answer. Must discuss tradeoffs, not just pick one option.",
    },
    {
        "id": "reason_h02", "type": "reasoning",
        "prompt": "A startup has $500k left and burns $50k/month. Revenue is $20k/month growing 15% monthly. Should they raise more funding, cut costs, or stay the course? Explain your reasoning with numbers.",
        "rubric": "Must calculate runway (~16-17 months factoring in growing revenue). Must weigh dilution cost of raising vs risk of running out. Must show quantitative reasoning, not just opinions.",
    },
    {
        "id": "reason_h03", "type": "reasoning",
        "prompt": "Explain why correlation does not imply causation using a real-world example that is NOT ice cream and drowning.",
        "rubric": "Must give a novel, clear example of spurious correlation. Must explain confounding variables. Must distinguish correlation from causation mechanism. Should mention possible tests (RCT, natural experiments).",
    },
    {
        "id": "reason_h04", "type": "reasoning",
        "prompt": "Your company's ML model achieves 99% accuracy on a fraud detection task where only 0.1% of transactions are fraudulent. Is this good? What metrics should you use instead?",
        "rubric": "Must identify the class imbalance problem (99.9% majority class). Must mention precision, recall, F1-score. Must explain why a 'predict all negative' baseline gets 99.9% accuracy. Should mention AUC-ROC or confusion matrix.",
    },
    {
        "id": "reason_h05", "type": "reasoning",
        "prompt": "A database query suddenly takes 100x longer than usual. Walk through a systematic debugging approach.",
        "rubric": "Must mention: check query plan (EXPLAIN), look for missing indexes, check table statistics/bloat, check for locks/contention, check if data volume changed. Must be systematic (not random guessing). Should mention monitoring/metrics.",
    },
    {
        "id": "reason_h06", "type": "reasoning",
        "prompt": "Explain the Byzantine Generals Problem and why it matters for blockchain consensus. What does it mean for a system to be Byzantine fault tolerant?",
        "rubric": "Must explain the problem: generals must agree on attack/retreat, some may be traitors. Must connect to distributed systems where nodes can fail arbitrarily. Must explain BFT = tolerating f faulty nodes out of 3f+1. Should connect to practical systems (PBFT, Tendermint).",
    },
    {
        "id": "reason_h07", "type": "reasoning",
        "prompt": "Why might a company choose eventual consistency over strong consistency for their database? Give a specific scenario where this tradeoff makes sense.",
        "rubric": "Must explain the CAP theorem connection. Must give a concrete scenario (e.g., social media likes, shopping cart). Must explain that eventual consistency enables higher availability and lower latency. Should mention the window of inconsistency tradeoff.",
    },
    {
        "id": "reason_h08", "type": "reasoning",
        "prompt": "Explain backpropagation in neural networks. Why does the vanishing gradient problem occur, and what solutions exist?",
        "rubric": "Must explain chain rule and gradient flow backward through layers. Must explain vanishing gradients: repeated multiplication of small values through many layers. Must mention solutions: ReLU, batch normalization, residual connections, LSTM. At least 3 solutions required.",
    },
    {
        "id": "reason_h09", "type": "reasoning",
        "prompt": "A hospital wants to use AI to triage emergency patients. What are the risks, and how would you design the system to be safe?",
        "rubric": "Must mention: bias in training data, liability/accountability, need for human oversight. Must propose guardrails: human-in-the-loop, explainability, continuous monitoring, fail-safe defaults. Must address fairness across demographics.",
    },
    {
        "id": "reason_h10", "type": "reasoning",
        "prompt": "Your microservice architecture has 15 services. Response time for the user-facing endpoint has gradually increased from 200ms to 2s over 3 months. How do you diagnose this?",
        "rubric": "Must mention distributed tracing (Jaeger/Zipkin). Must mention checking each service's latency independently. Should mention: cascading failures, connection pool exhaustion, N+1 queries, GC pauses, network congestion. Must be systematic.",
    },
]

# ─── Suite API ───────────────────────────────────────────────────────────────

ALL_TASKS = MATH_TASKS + CODE_TASKS + FACTUAL_TASKS + REASONING_TASKS
HARD_TASKS = MATH_HARD_TASKS + CODE_HARD_TASKS + REASONING_HARD_TASKS
FULL_TASKS = ALL_TASKS + HARD_TASKS

SUITES = {
    "math": MATH_TASKS,
    "math_hard": MATH_HARD_TASKS,
    "code": CODE_TASKS,
    "code_hard": CODE_HARD_TASKS,
    "factual": FACTUAL_TASKS,
    "reasoning": REASONING_TASKS,
    "reasoning_hard": REASONING_HARD_TASKS,
    "hard": HARD_TASKS,
    "standard": ALL_TASKS,
    "full": FULL_TASKS,
}


def get_suite(name: str = "full") -> list[dict]:
    """Get a task suite by name."""
    return SUITES.get(name, ALL_TASKS)


def get_random_tasks(n: int = 5, suite: str = "full") -> list[dict]:
    """Get n random tasks from a suite."""
    tasks = get_suite(suite)
    return random.sample(tasks, min(n, len(tasks)))


def list_suites() -> dict[str, int]:
    """List available suites and their task counts."""
    return {name: len(tasks) for name, tasks in SUITES.items()}
