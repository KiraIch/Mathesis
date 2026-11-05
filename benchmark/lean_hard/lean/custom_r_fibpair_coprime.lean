import Mathlib
namespace MathesisHard
def pr : ℕ → ℤ × ℤ
  | 0 => (0, 1)
  | n + 1 => ((pr n).2, (pr n).1 + (pr n).2)

theorem lean_custom_r_fibpair_coprime : ∀ n : ℕ, IsCoprime (pr n).1 (pr n).2 := by
  have key : ∀ m : ℕ, (pr m).2 ^ 2 - (pr m).2 * (pr m).1 - (pr m).1 ^ 2 = (-1) ^ m := by
    intro m
    induction m with
    | zero => simp [pr]
    | succ k ih =>
      simp only [pr, pow_succ]
      linear_combination (-1 : ℤ) * ih
  intro n
  refine ⟨-(-1) ^ n * (pr n).1, (-1) ^ n * ((pr n).2 - (pr n).1), ?_⟩
  have e : ((-1 : ℤ) ^ n) * (-1) ^ n = 1 := by rw [← mul_pow]; norm_num
  linear_combination ((-1 : ℤ) ^ n) * key n + e
end MathesisHard
