import Mathlib
namespace MathesisHard
theorem lean_logic_no_infinite_descent : ∀ f : ℕ → ℕ, ¬ ∀ n, f (n + 1) < f n := by
  intro f h
  have hb : ∀ n, f n + n ≤ f 0 := by
    intro n
    induction n with
    | zero => simp
    | succ k ih =>
      have := h k
      omega
  have := hb (f 0 + 1)
  omega
end MathesisHard
