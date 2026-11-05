import Mathlib
namespace MathesisHard
theorem lean_real_r_quad_fun_twenty : ∀ f : ℝ → ℝ, (∀ x y : ℝ, f (x + y) = f x + f y + 2 * x * y) → f 1 = 3 → f 20 = 440 := by
  intro f hf h1
  have h : ∀ n : ℕ, f (n : ℝ) = (n : ℝ) ^ 2 + 2 * (n : ℝ) := by
    intro n
    induction n with
    | zero =>
      have h0 := hf 0 0
      simp at h0 ⊢
      linarith
    | succ k ih =>
      have := hf (k : ℝ) 1
      push_cast
      rw [this, ih, h1]
      ring
  have h20 := h 20
  norm_num at h20
  exact h20
end MathesisHard
