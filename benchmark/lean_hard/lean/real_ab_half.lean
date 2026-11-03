import Mathlib
namespace MathesisHard
theorem lean_real_ab_half : ∀ a b : ℝ, 0 ≤ a → 0 ≤ b → a * b ≤ (a ^ 2 + b ^ 2) / 2 := by
  intro a b ha hb
  nlinarith [sq_nonneg (a - b)]
end MathesisHard
