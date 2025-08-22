import api from './http'
/**
 * 获取某学生在指定班型、购买数量下的单价（后端根据年级+班型+阶梯返回）
 * @param {number} studentId
 * @param {'one_to_one'|'one_to_two'|'small_class'} courseMode
 * @param {number} qty
 */
export function getUnitPriceByStudent(studentId, courseMode, qty = 1) {
  return api.get('billing/price', { params: { student_id: studentId, course_mode: courseMode, qty } })
}

/**
 * 创建购买订单（后端会再次校验与计算金额，前端不传金额）
 * payload: { student_id, course_mode, qty, discount_percent?, direct_off?, remark?, payment_method?, paid_at? }
 */
export function createPurchase(payload) {
  return api.post('billing/purchases', payload)
}
