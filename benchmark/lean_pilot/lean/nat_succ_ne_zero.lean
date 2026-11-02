namespace MathesisPilot
theorem lean_nat_succ_ne_zero : ∀ (n : Nat), Nat.succ n ≠ 0 := by
  intro n
  exact Nat.succ_ne_zero n
end MathesisPilot
