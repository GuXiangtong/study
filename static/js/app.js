// Image preview on upload
function previewImage(input) {
    var preview = document.getElementById('image-preview');
    if (!preview) return;
    if (input.files && input.files[0]) {
        var reader = new FileReader();
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(input.files[0]);
    } else {
        preview.style.display = 'none';
    }
}

// Toggle edit form for sub-questions
function toggleEditForm(id) {
    var form = document.getElementById('edit-form-' + id);
    if (form) {
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
    }
}

// Add sub-question row on create page
function addSubQuestion() {
    var container = document.getElementById('sub-questions-container');
    if (!container) return;
    var idx = container.children.length;
    var html = '<div class="sub-question-card">'
        + '<div class="form-row">'
        + '<div class="form-group" style="flex:0 0 80px"><label>标号</label>'
        + '<input type="text" name="sq_label" placeholder="(' + (idx+1) + ')" value="(' + (idx+1) + ')"></div>'
        + '<div class="form-group" style="flex:1"><label>子问题内容</label>'
        + '<input type="text" name="sq_content" placeholder="子问题文字描述（可选）"></div>'
        + '</div>'
        + '<div class="form-row">'
        + '<div class="form-group"><label>正确答案</label>'
        + '<textarea name="sq_correct_answer" rows="2" placeholder="正确答案或解题步骤"></textarea></div>'
        + '<div class="form-group"><label>学生错误答案</label>'
        + '<textarea name="sq_student_answer" rows="2" placeholder="学生当时的错误作答"></textarea></div>'
        + '</div>'
        + '<div class="form-row">'
        + '<div class="form-group"><label>出错原因（学生自述）</label>'
        + '<textarea name="sq_error_reason" rows="2" placeholder="为何做错？"></textarea></div>'
        + '<div class="form-group" style="flex:0 0 180px"><label>错误类型</label>'
        + '<select name="sq_error_type"><option value="">请选择</option>'
        + '<option value="概念不清">概念不清</option>'
        + '<option value="计算失误">计算失误</option>'
        + '<option value="思路缺失">思路缺失</option>'
        + '<option value="粗心">粗心</option></select></div>'
        + '</div></div>';
    container.insertAdjacentHTML('beforeend', html);
}
