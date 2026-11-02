namespace MathesisPilot
theorem lean_nat_le_succ_step : ∀ (n m : Nat), n ≤ m → n ≤ m + 1 := by
  intro n
  intro m
  intro h0
  have h : m ≤ m + 1 := Nat.le_succ m
  have h2 : n ≤ m + 1 := Nat.le_trans h0 h
  exact h2
end MathesisPilot
