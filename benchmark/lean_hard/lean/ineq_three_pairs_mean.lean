import Mathlib
namespace MathesisHard
theorem lean_ineq_three_pairs_mean : ∀ a b c : ℝ, 0 ≤ a → 0 ≤ b → 0 ≤ c → a * b + b * c + c * a ≤ (a + b + c) ^ 2 / 3 := by
  intro a b c ha hb hc
  nlinarith [sq_nonneg (a - b), sq_nonneg (b - c), sq_nonneg (c - a)]
end MathesisHard
