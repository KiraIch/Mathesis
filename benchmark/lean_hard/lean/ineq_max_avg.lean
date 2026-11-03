import Mathlib
namespace MathesisHard
theorem lean_ineq_max_avg : ∀ a b : ℝ, (a + b) / 2 ≤ max a b := by
  intro a b
  have h1 := le_max_left a b
  have h2 := le_max_right a b
  linarith
end MathesisHard
