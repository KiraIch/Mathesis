import Mathlib
namespace MathesisHard
theorem lean_real_cubic_root_exists : ∃ x : ℝ, 1 < x ∧ x < 2 ∧ x ^ 3 - 3 * x - 1 = 0 := by
  have hc : ContinuousOn (fun x : ℝ => x ^ 3 - 3 * x - 1) (Set.Icc 1 2) := by fun_prop
  have hm : (0:ℝ) ∈ Set.Icc ((fun x : ℝ => x ^ 3 - 3 * x - 1) 1) ((fun x : ℝ => x ^ 3 - 3 * x - 1) 2) := by
    constructor <;> norm_num
  obtain ⟨x, hx, hx0⟩ := intermediate_value_Icc (by norm_num : (1:ℝ) ≤ 2) hc hm
  simp only at hx0
  refine ⟨x, ?_, ?_, hx0⟩
  · rcases hx.1.lt_or_eq with h | h
    · exact h
    · subst h; norm_num at hx0
  · rcases hx.2.lt_or_eq with h | h
    · exact h
    · subst h; norm_num at hx0
end MathesisHard
