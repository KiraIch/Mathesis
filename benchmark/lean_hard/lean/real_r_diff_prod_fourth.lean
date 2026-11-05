import Mathlib
namespace MathesisHard
theorem lean_real_r_diff_prod_fourth : ∀ a b : ℝ, a - b = 2 → a * b = 3 → a ^ 4 + b ^ 4 = 82 := by
  intro a b h1 h2
  have h : a ^ 2 + b ^ 2 = 10 := by nlinarith [h1, h2]
  nlinarith [h, h2]
end MathesisHard
